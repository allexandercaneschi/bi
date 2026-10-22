(ns metabase.sso.integrations.all-oidc
  "ALL Tecnologias: endpoints of the Authentik (OIDC) login in the open source edition.

   Flow:
   1. GET /auth/sso/all-oidc (login button, or the app launch URL in Authentik)
   2. Metabase redirects to the provider's authorization endpoint, with an encrypted state cookie
   3. GET /auth/sso/all-oidc/callback?code=...&state=... validates the state and the ID token,
      finds (or creates) the user, syncs groups and opens the session."
  (:require
   [clojure.string :as str]
   [java-time.api :as t]
   [metabase.auth-identity.core :as auth-identity]
   [metabase.request.core :as request]
   [metabase.sso.core :as sso]
   [metabase.sso.oidc.state :as oidc.state]
   [metabase.sso.providers.all-oidc]
   [metabase.sso.settings :as sso.settings]
   [metabase.system.core :as system]
   [metabase.util.log :as log]
   [ring.util.response :as response]))

(set! *warn-on-reflection* true)

(defn- redirect-uri []
  (str (system/site-url) "/auth/sso/all-oidc/callback"))

(defn- escape-html [s]
  (-> (str s)
      (str/replace "&" "&amp;")
      (str/replace "<" "&lt;")
      (str/replace ">" "&gt;")
      (str/replace "\"" "&quot;")))

(defn- error-page
  "Plain page with the reason and a link back to the login, instead of a raw JSON error."
  [status message]
  (-> (response/response
       (str "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>Login único</title></head>"
            "<body style=\"font-family:sans-serif;background:#0f1720;color:#e6edf3;display:flex;"
            "align-items:center;justify-content:center;min-height:100vh;margin:0\">"
            "<div style=\"max-width:28rem;padding:2rem;text-align:center\">"
            "<h1 style=\"font-size:1.25rem\">Não foi possível entrar com o login único</h1>"
            "<p>" (escape-html message) "</p>"
            "<p><a style=\"color:#35A8E0\" href=\"/auth/login\">Voltar para o login</a></p>"
            "</div></body></html>"))
      (response/status status)
      (response/content-type "text/html; charset=utf-8")))

(defn sso-initiate
  "Redirects to the provider's authorization endpoint."
  [request]
  (if-not (sso.settings/all-oidc-enabled)
    (error-page 404 "O login único não está configurado neste servidor.")
    (let [redirect (or (some-> (get-in request [:params :redirect]) not-empty) "/")]
      (if-not (oidc.state/valid-redirect-url? redirect)
        (error-page 400 "Endereço de retorno inválido.")
        (let [auth-result (auth-identity/authenticate :provider/all-oidc
                                                      (assoc request :redirect-uri (redirect-uri)))]
          (if (= :redirect (:success? auth-result))
            (sso/wrap-oidc-redirect auth-result request :all-oidc redirect
                                    {:browser-id (:browser-id request)})
            (do (log/errorf "ALL OIDC: could not start the login: %s" (:message auth-result))
                (error-page 500 "O provedor de login não respondeu. Tente novamente em instantes."))))))))

(defn sso-callback
  "Handles the provider callback and opens the Metabase session."
  [request]
  (if-not (sso.settings/all-oidc-enabled)
    (error-page 404 "O login único não está configurado neste servidor.")
    (let [{:keys [code state error_description]} (:params request)
          login-result (auth-identity/login! :provider/all-oidc
                                             (assoc request
                                                    :code code
                                                    :state state
                                                    :oidc-provider :all-oidc
                                                    :redirect-uri (redirect-uri)
                                                    :device-info (request/device-info request)))]
      (if (and (:success? login-result) (:session login-result))
        (request/set-session-cookies request
                                     (-> (response/redirect (or (:redirect-url login-result) "/"))
                                         sso/clear-oidc-state-cookie)
                                     (:session login-result)
                                     (t/zoned-date-time (t/zone-id "GMT")))
        (do (log/warnf "ALL OIDC: login failed: %s (%s)" (:message login-result) (:error login-result))
            (-> (error-page 401 (if (= :account-creation-not-allowed (:error login-result))
                                  (:message login-result)
                                  (or error_description "A autenticação falhou ou expirou. Tente entrar de novo.")))
                sso/clear-oidc-state-cookie))))))
