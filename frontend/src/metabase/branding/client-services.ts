/**
 * ALL Tecnologias — filtragem por cliente e serviços contratados à parte.
 *
 * O SQL das perguntas usa marcadores __ALL_<CÓDIGO>__ (ex.: __ALL_ERP__), trocados no servidor pelos
 * códigos do grupo de cliente (src/metabase/query_processor/middleware/all_client_scope.clj).
 * A equipe da ALL escolhe o cliente pelo filtro de painel com slug "cliente", ligado à variável
 * {{all_cliente}} das perguntas. Para usuários de cliente esse filtro fica escondido.
 */

/** Slug do filtro "Cliente" dos painéis (escondido para usuários de cliente). */
export const ALL_CLIENT_PARAMETER_SLUG = "cliente";

export interface AllClientGroupConfig {
  codes?: Record<string, string>;
  services?: Record<string, boolean>;
}

/** Valor da configuração `all-client-group-config`: id do grupo → configuração. */
export type AllClientGroupConfigMap = Record<string, AllClientGroupConfig>;

export interface AllClientCodeField {
  key: string;
  label: string;
  description: string;
  placeholder: string;
}

/** Códigos de cada sistema. O marcador no SQL é __ALL_<KEY EM MAIÚSCULAS>__. */
export const ALL_CLIENT_CODE_FIELDS: AllClientCodeField[] = [
  {
    key: "erp",
    label: "ERP (AML)",
    description: "Códigos dos clientes no ERP, separados por vírgula.",
    placeholder: "6,7,23",
  },
  {
    key: "tactical",
    label: "Tactical RMM",
    description: "Nome do cliente no Tactical.",
    placeholder: "Tecmar",
  },
  {
    key: "zabbix",
    label: "Zabbix",
    description:
      "Nome do grupo de hosts do cliente, como aparece no Zabbix. Mais de um: separe por vírgula.",
    placeholder: "Tecmar",
  },
  {
    key: "bacula",
    label: "Bacula",
    description:
      "ClientId do cliente no Bacula. Mais de um: separe por vírgula.",
    placeholder: "6",
  },
  {
    key: "wazuh",
    label: "Wazuh (auditoria de arquivos)",
    description: "Schema do cliente no banco da auditoria.",
    placeholder: "cli_tecmar",
  },
  {
    key: "squid",
    label: "Squid (histórico de navegação)",
    description: "Identificador do cliente nos logs de navegação.",
    placeholder: "tecmar",
  },
];

export interface AllClientService {
  key: string;
  /** Nome do serviço e título da aba. */
  title: string;
  /** Texto curto para o gestor do cliente (sem termos técnicos). */
  pitch: string;
  /** Reconhece a aba do painel que mostra este serviço, pelo nome. */
  tabNamePattern: RegExp;
}

export const ALL_CLIENT_SERVICES: AllClientService[] = [
  {
    key: "auditoria",
    title: "Auditoria de Arquivos",
    pitch:
      "Saiba quem criou, alterou, copiou ou apagou cada arquivo da empresa, e quando. Alertas para exclusões fora do horário e histórico completo para recuperar o que sumiu.",
    tabNamePattern: /auditoria/i,
  },
  {
    key: "navegacao",
    title: "Histórico de Navegação",
    pitch:
      "Veja quais sites são acessados na empresa, por quem e quanto tempo. Relatórios por usuário e por categoria, com bloqueios sob medida.",
    tabNamePattern: /navega/i,
  },
];

export const ALL_COMMERCIAL_CONTACT = {
  whatsappNumber: "5532987133380",
  whatsappLabel: "(32) 9 8713-3380",
  email: "comercial@alltecnologias.com.br",
};

export function getServiceForTabName(
  tabName: string | undefined,
): AllClientService | undefined {
  if (!tabName) {
    return undefined;
  }
  return ALL_CLIENT_SERVICES.find((service) =>
    service.tabNamePattern.test(tabName),
  );
}

export function getWhatsappUrl(service: AllClientService) {
  const text = `Olá! Tenho interesse no serviço ${service.title} da ALL Tecnologias.`;
  return `https://wa.me/${ALL_COMMERCIAL_CONTACT.whatsappNumber}?text=${encodeURIComponent(text)}`;
}

export function getEmailUrl(service: AllClientService) {
  const subject = `Interesse em ${service.title}`;
  const body = `Olá! Tenho interesse no serviço ${service.title} da ALL Tecnologias.`;
  return `mailto:${ALL_COMMERCIAL_CONTACT.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
