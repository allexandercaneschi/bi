import { useEffect, useState } from "react";
import { t } from "ttag";

import { useAdminSetting } from "metabase/api/utils";
import {
  ALL_CLIENT_CODE_FIELDS,
  ALL_CLIENT_SERVICES,
  type AllClientGroupConfig,
} from "metabase/branding/client-services";
import { Box, Button, Group, Stack, Switch, Text, TextInput, Title } from "metabase/ui";
import type { Group as PermissionsGroup } from "metabase-types/api";

const VALID_CODE = /^(?!.*--)[\p{L}\p{N} _.,:/-]*$/u;

interface ClientGroupConfigProps {
  group: PermissionsGroup;
}

/**
 * ALL Tecnologias: códigos do cliente em cada sistema e serviços contratados à parte.
 * Os códigos substituem os marcadores __ALL_<CÓDIGO>__ no SQL das perguntas. Os interruptores de
 * serviço só controlam o que o cliente vê; a equipe da ALL continua vendo os dados no painel do suporte.
 */
export const ClientGroupConfig = ({ group }: ClientGroupConfigProps) => {
  const { value, updateSetting, isLoading } = useAdminSetting(
    "all-client-group-config",
  );
  const groupKey = String(group.id);
  const saved: AllClientGroupConfig = value?.[groupKey] ?? {};

  const [codes, setCodes] = useState<Record<string, string>>({});
  const [services, setServices] = useState<Record<string, boolean>>({});
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setCodes(saved.codes ?? {});
    setServices(saved.services ?? {});
    // only reset when the stored value for this group changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(saved)]);

  const invalidKeys = ALL_CLIENT_CODE_FIELDS.filter(
    (field) => !VALID_CODE.test(codes[field.key] ?? ""),
  ).map((field) => field.key);
  const hasErrors = invalidKeys.length > 0;

  const handleSave = async () => {
    const cleanCodes = Object.fromEntries(
      Object.entries(codes)
        .map(([key, code]): [string, string] => [key, code.trim()])
        .filter(([, code]) => code.length > 0),
    );
    setIsSaving(true);
    await updateSetting({
      key: "all-client-group-config",
      value: {
        ...(value ?? {}),
        [groupKey]: { codes: cleanCodes, services },
      },
    });
    setIsSaving(false);
  };

  return (
    <Box
      maw="38rem"
      mb="xl"
      p="lg"
      bd="1px solid var(--mb-color-border)"
      bdrs="md"
      bg="background-primary"
    >
      <Stack gap="lg">
        <Box>
          <Title order={4}>{t`Códigos do cliente`}</Title>
          <Text c="text-secondary" size="sm">
            {t`Usados no lugar dos marcadores __ALL_ERP__, __ALL_ZABBIX__ etc. nas perguntas. Deixe em branco o que o cliente não usa.`}
          </Text>
        </Box>
        {ALL_CLIENT_CODE_FIELDS.map((field) => (
          <TextInput
            key={field.key}
            label={field.label}
            description={`${field.description} · __ALL_${field.key.toUpperCase()}__`}
            placeholder={field.placeholder}
            value={codes[field.key] ?? ""}
            error={
              invalidKeys.includes(field.key)
                ? t`Use só letras, números, espaço, vírgula, ponto, barra, hífen e sublinhado (sem "--").`
                : undefined
            }
            onChange={(event) =>
              setCodes({ ...codes, [field.key]: event.currentTarget.value })
            }
          />
        ))}

        <Box>
          <Title order={4}>{t`Serviços contratados`}</Title>
          <Text c="text-secondary" size="sm">
            {t`Desligado: o cliente vê a aba com uma prévia desfocada e o convite para contratar. A equipe da ALL continua vendo os dados.`}
          </Text>
        </Box>
        {ALL_CLIENT_SERVICES.map((service) => (
          <Switch
            key={service.key}
            label={service.title}
            checked={Boolean(services[service.key])}
            onChange={(event) =>
              setServices({
                ...services,
                [service.key]: event.currentTarget.checked,
              })
            }
          />
        ))}

        <Group justify="flex-end">
          <Button
            variant="filled"
            onClick={handleSave}
            disabled={isLoading || hasErrors}
            loading={isSaving}
          >
            {t`Salvar configuração do cliente`}
          </Button>
        </Group>
      </Stack>
    </Box>
  );
};
