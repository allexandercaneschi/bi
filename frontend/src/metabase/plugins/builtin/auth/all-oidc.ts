// ALL Tecnologias: login único via Authentik (OIDC) na edição open source.
import { PLUGIN_AUTH_PROVIDERS } from "metabase/plugins";
import MetabaseSettings from "metabase/utils/settings";

PLUGIN_AUTH_PROVIDERS.providers.push((providers) => {
  const allOidcProvider = {
    name: "all-oidc",
    // circular dependencies
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    Button: require("metabase/auth/components/AllOidcButton").AllOidcButton,
  };

  return MetabaseSettings.get("all-oidc-enabled")
    ? [allOidcProvider, ...providers]
    : providers;
});
