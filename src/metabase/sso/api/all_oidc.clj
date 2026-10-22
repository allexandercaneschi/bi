(ns metabase.sso.api.all-oidc
  "ALL Tecnologias: routes of the Authentik (OIDC) login in the open source edition."
  (:require
   [metabase.api.macros :as api.macros]
   [metabase.sso.integrations.all-oidc :as all-oidc]))

;; GET /auth/sso/all-oidc
;;
#_{:clj-kondo/ignore [:metabase/validate-defendpoint-has-response-schema]}
(api.macros/defendpoint :get "/"
  "Start the SSO login (also the app launch URL in Authentik)."
  [_route-params _query-params _body request]
  (all-oidc/sso-initiate request))

;; GET /auth/sso/all-oidc/callback
;;
#_{:clj-kondo/ignore [:metabase/validate-defendpoint-has-response-schema]}
(api.macros/defendpoint :get "/callback"
  "SSO login callback."
  [_route-params _query-params _body request]
  (all-oidc/sso-callback request))

(def ^{:arglists '([request respond raise])} routes
  "`/auth/sso/all-oidc` routes."
  (api.macros/ns-handler *ns*))
