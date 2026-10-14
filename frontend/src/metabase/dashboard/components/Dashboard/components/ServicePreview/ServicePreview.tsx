import { t } from "ttag";

import {
  ALL_COMMERCIAL_CONTACT,
  type AllClientService,
  getEmailUrl,
  getWhatsappUrl,
} from "metabase/branding/client-services";
import { Button, Group, Stack, Text, Title } from "metabase/ui";

import S from "./ServicePreview.module.css";

// Dados inventados só para a prévia desfocada: nada vem do banco.
const FAKE_KPIS = [
  { label: "Eventos (7 dias)", value: "1.284" },
  { label: "Arquivos alterados", value: "312" },
  { label: "Exclusões", value: "27" },
  { label: "Alertas críticos", value: "3" },
];
const FAKE_BARS = [38, 52, 44, 70, 61, 25, 18, 47, 66, 58, 73, 40, 35, 55];
const FAKE_ROWS = ["ok", "warning", "ok", "critical", "ok", "warning"] as const;

const DOT_CLASS = {
  ok: S.dotOk,
  warning: S.dotWarning,
  critical: S.dotCritical,
};

interface ServicePreviewProps {
  service: AllClientService;
}

/**
 * ALL Tecnologias: aba de serviço não contratado. Mostra uma prévia desfocada com dados fictícios e o
 * convite para contratar (WhatsApp ou e-mail). Os cartões reais da aba não são carregados.
 */
export const ServicePreview = ({ service }: ServicePreviewProps) => (
  <div className={S.root} data-testid="all-service-preview">
    <div className={S.preview} aria-hidden="true">
      {FAKE_KPIS.map((kpi) => (
        <div key={kpi.label} className={S.card}>
          <div className={S.label}>{kpi.label}</div>
          <div className={S.kpi}>{kpi.value}</div>
        </div>
      ))}
      <div className={`${S.card} ${S.wide}`}>
        <div className={S.label}>{t`Por dia`}</div>
        <div className={S.bars}>
          {FAKE_BARS.map((height, index) => (
            <div key={index} className={S.bar} style={{ height: `${height}%` }} />
          ))}
        </div>
      </div>
      <div className={`${S.card} ${S.wide}`}>
        <div className={S.label}>{t`Por usuário`}</div>
        <div className={S.bars}>
          {FAKE_BARS.slice(0, 7)
            .reverse()
            .map((height, index) => (
              <div key={index} className={S.bar} style={{ height: `${height}%` }} />
            ))}
        </div>
      </div>
      <div className={`${S.card} ${S.full}`}>
        <div className={S.label}>{t`Eventos recentes`}</div>
        {FAKE_ROWS.map((status, index) => (
          <div key={index} className={S.row}>
            <div className={S.cell} />
            <div className={S.cell} />
            <div className={S.cell} />
            <div className={DOT_CLASS[status]} />
          </div>
        ))}
      </div>
    </div>

    <div className={S.overlay}>
      <div className={S.invite}>
        <Stack gap="md">
          <div>
            <span className={S.badge}>{t`Serviço não contratado`}</span>
          </div>
          <Title order={2}>{service.title}</Title>
          <Text c="text-primary">{service.pitch}</Text>
          <Text c="text-secondary" size="sm">
            {t`Quer ver estas informações da sua empresa aqui? Fale com a gente pelo canal que preferir.`}
          </Text>
          <Group gap="sm">
            <Button
              component="a"
              href={getWhatsappUrl(service)}
              target="_blank"
              rel="noopener noreferrer"
              variant="filled"
            >
              {t`WhatsApp ${ALL_COMMERCIAL_CONTACT.whatsappLabel}`}
            </Button>
            <Button component="a" href={getEmailUrl(service)} variant="default">
              {t`E-mail comercial`}
            </Button>
          </Group>
        </Stack>
      </div>
    </div>
  </div>
);
