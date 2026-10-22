(ns metabase.sso.integrations.all-oidc-test
  "ALL Tecnologias: tests of the Authentik (OIDC) login in the open source edition."
  (:require
   [clojure.string :as str]
   [clojure.test :refer :all]
   [metabase.app-db.encryption-test-util :as encryption-tu]
   [metabase.auth-identity.core :as auth-identity]
   [metabase.sso.providers.all-oidc :as all-oidc]
   [metabase.sso.settings :as sso.settings]
   [metabase.sso.test-helpers :as sso.test-helpers]
   [metabase.test :as mt]
   [metabase.test.fixtures :as fixtures]
   [metabase.test.http-client :as client]
   [metabase.util.encryption :as encryption]
   [methodical.core :as methodical]
   [toucan2.core :as t2]))

(set! *warn-on-reflection* true)

(def ^:private test-secret
  (encryption/secret-key->hash "Orw0AAyzkO/kPTLJRxiyKoBHXa/d6ZcO+p+gpZO/wSQ="))

(use-fixtures :once
  (fixtures/initialize :test-users)
  (encryption-tu/with-encrypted-app-db-fixture test-secret))

(use-fixtures :each (fn [thunk] (binding [client/*url-prefix* ""] (thunk))))

(def ^:private test-email "maria.authentik@alltecnologias.com.br")

;; Stands in for the base OIDC provider: no real token exchange or JWKS.
(methodical/defmethod auth-identity/authenticate :provider/test-all-oidc-idp
  [_provider request]
  (if (some #(contains? request %) [:code :error :state])
    {:success?    true
     :claims      {:email test-email :name "Maria da Silva" :groups ["bi-tecmar"]}
     :user-data   {:email test-email :sso_source :oidc}
     :provider-id "authentik-sub"}
    {:success?     :redirect
     :redirect-url "https://auth.example.com/application/o/authorize/?client_id=bi"
     :state        "test-state"
     :nonce        "test-nonce"}))

(methodical/prefer-method! #'auth-identity/authenticate :provider/test-all-oidc-idp :provider/oidc)

(defmacro ^:private with-fake-idp! [& body]
  `(try
     (derive :provider/all-oidc :provider/test-all-oidc-idp)
     ~@body
     (finally
       (underive :provider/all-oidc :provider/test-all-oidc-idp))))

(defmacro ^:private with-all-oidc-config! [env & body]
  `(encryption-tu/with-encrypted-app-db
     (mt/with-temporary-setting-values [~'site-url (sso.test-helpers/localhost-site-url)]
       (mt/with-temp-env-var-value! [~'mb-all-oidc-issuer        "https://auth.example.com/application/o/bi/"
                                     ~'mb-all-oidc-client-id     "bi"
                                     ~'mb-all-oidc-client-secret "secret"
                                     ~@env]
         ~@body))))

(defn- login!
  "Starts the login, then calls the callback with the state cookie. Returns the callback response."
  [expected-status]
  (let [init     (mt/client-full-response :get 302 "/auth/sso/all-oidc"
                                          {:request-options {:redirect-strategy :none}})
        cookies  (->> (get-in init [:headers "Set-Cookie"])
                      (map #(first (str/split % #";")))
                      (str/join "; "))]
    (mt/client-real-response :get expected-status "/auth/sso/all-oidc/callback"
                             {:request-options {:redirect-strategy :none
                                                :headers           {"Cookie" cookies}}}
                             :code "test-code"
                             :state "test-state")))

(deftest names-from-claims-test
  (is (= ["Maria" "da Silva"] (#'all-oidc/names-from-claims {:name "Maria da Silva" :given_name "Maria da Silva"})))
  (is (= ["Maria"] (#'all-oidc/names-from-claims {:name "Maria"})))
  (is (= ["Ana" "Souza"] (#'all-oidc/names-from-claims {:name "Ana Souza" :given_name "Ana" :family_name "Souza"}))))

(deftest ^:synchronized not-configured-test
  (testing "without the MB_ALL_OIDC_* variables the login is not available"
    (mt/with-temp-env-var-value! [mb-all-oidc-issuer nil mb-all-oidc-client-id nil mb-all-oidc-client-secret nil]
      (is (false? (sso.settings/all-oidc-enabled)))
      (is (str/includes? (str (mt/client :get 404 "/auth/sso/all-oidc"))
                         "não está configurado")))))

(deftest ^:synchronized redirect-test
  (with-all-oidc-config! []
    (with-fake-idp!
      (let [response (mt/client-full-response :get 302 "/auth/sso/all-oidc"
                                              {:request-options {:redirect-strategy :none}})]
        (is (str/starts-with? (get-in response [:headers "Location"]) "https://auth.example.com/"))
        (is (some #(str/includes? % "metabase.OIDC_STATE") (get-in response [:headers "Set-Cookie"])))))))

(deftest ^:synchronized unknown-user-without-auto-create-test
  (testing "a user without a Metabase account is refused when auto creation is off"
    (with-all-oidc-config! []
      (with-fake-idp!
        (mt/with-model-cleanup [:model/User]
          (t2/delete! :model/User :email test-email)
          (let [response (login! 401)]
            (is (str/includes? (str (:body response)) "Peça ao administrador"))
            (is (not (t2/exists? :model/User :email test-email)))))))))

(deftest ^:synchronized create-user-and-sync-groups-test
  (testing "with auto creation on, the user is created, named and put in the mapped groups"
    (mt/test-helpers-set-global-values!
      (with-all-oidc-config! [:mb-all-oidc-auto-create-users "true"
                              :mb-all-oidc-group-mappings
                              "{\"bi-tecmar\": [\"Cliente Tecmar (all-oidc test)\"], \"bi-outro\": \"Outro (all-oidc test)\"}"]
        (mt/with-temp [:model/PermissionsGroup {tecmar-id :id} {:name "Cliente Tecmar (all-oidc test)"}
                       :model/PermissionsGroup {other-id :id}  {:name "Outro (all-oidc test)"}]
          (with-fake-idp!
            (mt/with-model-cleanup [:model/User]
              (t2/delete! :model/User :email test-email)
              (let [response (login! 302)
                    user     (t2/select-one :model/User :email test-email)
                    groups   (t2/select-fn-set :group_id :model/PermissionsGroupMembership
                                               :user_id (:id user) :group_id [:in [tecmar-id other-id]])]
                (is (sso.test-helpers/successful-login? response))
                (is (= "/" (get-in response [:headers "Location"])))
                (is (= ["Maria" "da Silva" :all-oidc] ((juxt :first_name :last_name :sso_source) user)))
                (is (= #{tecmar-id} groups))))))))))
