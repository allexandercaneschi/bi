import cx from "classnames";

import { useSetting } from "metabase/common/hooks";
import { Icon } from "metabase/ui";

import S from "../AuthButton/AuthButton.module.css";

interface AllOidcButtonProps {
  redirectUrl?: string;
  isCard?: boolean;
}

/**
 * ALL Tecnologias: botão do login único (Authentik). Navegação completa (não é rota do
 * frontend), porque o fluxo passa pelo provedor e volta em /auth/sso/all-oidc/callback.
 */
export const AllOidcButton = ({ redirectUrl, isCard }: AllOidcButtonProps) => {
  const label = useSetting("all-oidc-button-label");
  const href = redirectUrl
    ? `/auth/sso/all-oidc?redirect=${encodeURIComponent(redirectUrl)}`
    : "/auth/sso/all-oidc";

  return (
    <a href={href} className={cx(S.link, { [S.card]: isCard })}>
      <Icon name="key" mr="sm" />
      {label || "Entrar com SSO"}
    </a>
  );
};
