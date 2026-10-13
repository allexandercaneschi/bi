/**
 * ALL Tecnologias — branding do fork do Metabase (AGPL).
 *
 * Nome e mensagens do frontend ficam aqui. As CORES e o nome usado no
 * backend (título da aba, e-mails) ficam em src/metabase/appearance/settings.clj.
 * Os arquivos de imagem ficam em:
 *   resources/frontend_client/app/assets/img/all-logo-horizontal.svg (barra superior: ícone + "ALL Tecnologias")
 *   resources/frontend_client/app/assets/img/all-logo-icon.svg       (ícone: login, admin, menus)
 *   resources/frontend_client/app/assets/img/favicon.ico    (ícone da aba)
 *   resources/frontend_client/app/assets/img/email_logo.png (logo dos e-mails)
 */
import logoHorizontalUrl from "assets/img/all-logo-horizontal.svg";
import logoUrl from "assets/img/all-logo-icon.svg";

interface BrandConfig {
  name: string;
  logoUrl: string;
  logoHorizontalUrl: string;
  loadingMessage: string;
  slowLoadingMessage: string;
  showMetabaseLinks: boolean;
}

export const BRAND: BrandConfig = {
  /** Substitui a palavra "Metabase" em toda a interface. */
  name: "B.I ALL Tecnologias",

  /** Ícone oficial (símbolo do chip), para espaços quadrados. */
  logoUrl,

  /** Logo horizontal (ícone + "ALL Tecnologias") da barra superior. */
  logoHorizontalUrl,

  /** Mensagens exibidas enquanto uma consulta roda. */
  loadingMessage: "Carregando dados...",
  slowLoadingMessage: "Aguardando resultados...",

  /** Esconde links para metabase.com (docs, ajuda, upsells) fora do admin. */
  showMetabaseLinks: false,
};
