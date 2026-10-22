(ns metabase.sso.providers.all-oidc
  "ALL Tecnologias: login via Authentik (or any OIDC provider) in the open source edition.

   Derives from the base OIDC provider ([[metabase.sso.providers.oidc]]) and adds:
   - configuration from the `all-oidc-*` settings (MB_ALL_OIDC_* environment variables);
   - optional account creation on the first login;
   - group sync from the provider's `groups` claim, using `all-oidc-group-mappings`."
  (:require
   [clojure.string :as str]
   [metabase.auth-identity.core :as auth-identity]
   [metabase.sso.common :as sso.common]
   [metabase.sso.settings :as sso.settings]
   [metabase.util.log :as log]
   [methodical.core :as methodical]
   [toucan2.core :as t2]))

(set! *warn-on-reflection* true)

(derive :provider/all-oidc :provider/oidc)

(defn- oidc-config
  [request]
  {:client-id     (sso.settings/all-oidc-client-id)
   :client-secret (sso.settings/all-oidc-client-secret)
   :issuer-uri    (sso.settings/all-oidc-issuer)
   :scopes        ["openid" "email" "profile"]
   :redirect-uri  (:redirect-uri request)})

(defn- names-from-claims
  "Authentik sends the full name in `name` (and `given_name`), without `family_name`.
   Splits it into first and last name; falls back to the standard claims."
  [claims]
  (let [full-name (some-> (or (:name claims) (:given_name claims)) str/trim not-empty)]
    (if (and full-name (str/blank? (:family_name claims)))
      (str/split full-name #"\s+" 2)
      [(:given_name claims) (:family_name claims)])))

(methodical/defmethod auth-identity/authenticate :provider/all-oidc
  [provider request]
  (if-not (sso.settings/all-oidc-enabled)
    {:success? false
     :error    :all-oidc-not-configured
     :message  "SSO login is not configured"}
    (let [result (next-method provider (assoc request :oidc-config (oidc-config request)))]
      (if (and (true? (:success? result)) (:user-data result))
        (let [claims                 (:claims result)
              [first-name last-name] (names-from-claims claims)]
          (-> result
              (update :user-data assoc
                      :first_name first-name
                      :last_name  last-name
                      :sso_source :all-oidc)
              (assoc :all-oidc-groups (vec (:groups claims)))))
        result))))

(defn- group-mappings
  "`all-oidc-group-mappings` as {provider group name -> [Metabase group names]}."
  []
  (into {}
        (map (fn [[k v]] [(name k) (if (string? v) [v] (vec v))]))
        (sso.settings/all-oidc-group-mappings)))

(defn- sync-groups!
  "Puts the user in the Metabase groups mapped from their provider groups. Only mapped Metabase
   groups are touched; memberships in other groups are kept."
  [user provider-groups]
  (let [mappings (group-mappings)]
    (when (seq mappings)
      (let [name->id (t2/select-fn->fn :name :id :model/PermissionsGroup)
            ids      (fn [group-names] (keep name->id group-names))
            mapped   (set (mapcat ids (vals mappings)))
            wanted   (set (mapcat (comp ids mappings) provider-groups))]
        (doseq [group-name (apply concat (vals mappings))
                :when      (not (name->id group-name))]
          (log/warnf "ALL OIDC: Metabase group %s in all-oidc-group-mappings does not exist" (pr-str group-name)))
        (sso.common/sync-group-memberships! user wanted mapped)))))

(methodical/defmethod auth-identity/login! :provider/all-oidc
  [provider {:keys [user] :as request}]
  (cond
    (not (true? (:success? request)))
    request

    (and (not user) (not (sso.settings/all-oidc-auto-create-users)))
    {:success? false
     :error    :account-creation-not-allowed
     :message  "Você ainda não tem conta no B.I. Peça ao administrador para criar seu acesso."}

    :else
    (let [result (next-method provider request)]
      (when-let [logged-in-user (:user result)]
        (sync-groups! logged-in-user (:all-oidc-groups request)))
      result)))
