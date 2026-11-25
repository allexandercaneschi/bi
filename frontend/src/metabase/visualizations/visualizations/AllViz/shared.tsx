/**
 * ALL Tecnologias: base das visualizações próprias do ALL B.I.
 *
 * Cada visualização é registrada com o identificador "custom:all-..." (ver index.ts) e aparece, em qualquer
 * pergunta de qualquer painel, no seletor de visualização, em "Visualizações personalizadas".
 * As visualizações leem as colunas do resultado do SQL pelo NOME da coluna (sem acento e sem diferenciar
 * maiúsculas), então o contrato de cada uma está descrito no topo do seu arquivo.
 */
import type { CSSProperties, MouseEvent, ReactNode } from "react";

import { columnSettings } from "metabase/visualizations/lib/settings/column";
import type {
  VisualizationDefinition,
  VisualizationProps,
} from "metabase/visualizations/types";

export const VERDE = "#1baf7a";
export const CINZA = "#a3a29a";
export const LARANJA = "#eb6834";
export const AMARELO = "#eda100";
export const AZUL = "#35a8e0";
export const ROXO = "#7b61ff";
export const PARADO = "#5b6b82";

/** Cores fixas dos tipos de uso: verde = produtivo, cinza = neutro, laranja = fora do trabalho. */
const CORES_NOMEADAS: Record<string, string> = {
  produtivo: VERDE,
  neutro: CINZA,
  "fora do trabalho": LARANJA,
  improdutivo: LARANJA,
  parado: PARADO,
  verde: VERDE,
  cinza: CINZA,
  laranja: LARANJA,
  amarelo: AMARELO,
  azul: AZUL,
  roxo: ROXO,
  ok: VERDE,
  atencao: AMARELO,
  alerta: LARANJA,
};

export function semAcento(texto: unknown): string {
  return String(texto ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .trim()
    .toLowerCase();
}

export function corDe(nome: unknown, padrao: string = AZUL): string {
  const chave = semAcento(nome);
  if (CORES_NOMEADAS[chave]) {
    return CORES_NOMEADAS[chave];
  }
  if (/^#[0-9a-f]{3,8}$/i.test(String(nome ?? "").trim())) {
    return String(nome).trim();
  }
  return padrao;
}

/** Cor de uma situação de computador (texto vindo de bi.dispositivos.situacao). */
export function corDaSituacao(situacao: unknown): string {
  const s = semAcento(situacao);
  if (s.startsWith("em uso")) {
    return VERDE;
  }
  if (s.includes("mais de 1 dia") || s.includes("nunca")) {
    return LARANJA;
  }
  if (s.includes("hoje")) {
    return AMARELO;
  }
  return PARADO;
}

/** "há 5 min", "há 3 h", "há 2 dias" para datas; null se o valor não for data. */
export function tempoRelativo(valor: unknown, agora: number = Date.now()): string | null {
  if (valor == null || ehNumero(valor)) {
    return null;
  }
  const t = Date.parse(String(valor));
  if (!Number.isFinite(t)) {
    return null;
  }
  const min = Math.round((agora - t) / 60000);
  if (min < 1) {
    return "agora";
  }
  if (min < 60) {
    return `há ${min} min`;
  }
  const h = Math.round(min / 60);
  if (h < 24) {
    return `há ${h} h`;
  }
  const d = Math.round(h / 24);
  return d === 1 ? "há 1 dia" : `há ${d} dias`;
}

/** Data e hora no padrão ALL, ano primeiro (2026/11/24 - 17:58), no fuso do navegador; vazio se não for data. */
export function dataHora(valor: unknown): string {
  const t = Date.parse(String(valor ?? ""));
  if (!Number.isFinite(t)) {
    return "";
  }
  const d = new Date(t);
  const dois = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}/${dois(d.getMonth() + 1)}/${dois(d.getDate())}` +
    ` - ${dois(d.getHours())}:${dois(d.getMinutes())}`
  );
}

/** Acerta acentos de textos que vêm sem acento do banco (ex.: "ha mais de 1 dia"). */
export function comAcento(texto: string): string {
  return texto.replace(/\bha\b/g, "há");
}

type Dados = VisualizationProps["series"][number]["data"];

export function dadosDe(props: VisualizationProps): Dados {
  return props.series[0].data;
}

/** Índice da primeira coluna cujo nome (ou nome de exibição) bate com algum dos nomes dados; -1 se nenhuma. */
export function achaColuna(cols: Dados["cols"], nomes: string[]): number {
  const alvo = nomes.map(semAcento);
  return cols.findIndex(
    (c) =>
      alvo.includes(semAcento(c.name)) ||
      alvo.includes(semAcento(c.display_name)),
  );
}

export function ehNumero(valor: unknown): boolean {
  return typeof valor === "number" && Number.isFinite(valor);
}

export function colunaNumerica(cols: Dados["cols"], rows: Dados["rows"], i: number) {
  const base = String(cols[i]?.base_type ?? "");
  return (
    base.includes("Integer") ||
    base.includes("Float") ||
    base.includes("Decimal") ||
    base.includes("BigInteger") ||
    (rows.length > 0 && rows.some((r) => ehNumero(r[i])))
  );
}

export function formataNumero(valor: unknown, casas = 1): string {
  if (!ehNumero(valor)) {
    return valor == null ? "" : String(valor);
  }
  return (valor as number).toLocaleString("pt-BR", {
    maximumFractionDigits: casas,
  });
}

export function iniciais(nome: unknown): string {
  const partes = String(nome ?? "")
    .replace(/[._-]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (partes.length === 0) {
    return "?";
  }
  if (partes.length === 1) {
    return partes[0].slice(0, 2).toUpperCase();
  }
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
}

/** Cor estável por nome (para o círculo com as iniciais). */
export function corDoNome(nome: unknown): string {
  const paleta = [AZUL, ROXO, VERDE, AMARELO, "#e0508a", "#3fb7b0", "#8e7cc3"];
  let h = 0;
  for (const ch of String(nome ?? "")) {
    h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  }
  return paleta[h % paleta.length];
}

export function clicavel(
  props: VisualizationProps,
  rowIndex: number,
  colIndex: number,
): boolean {
  const { series, settings, visualizationIsClickable, onVisualizationClick } =
    props;
  if (!onVisualizationClick || !visualizationIsClickable) {
    return false;
  }
  const { rows, cols } = series[0].data;
  const row = rows[rowIndex];
  if (!row || colIndex < 0) {
    return false;
  }
  return Boolean(
    visualizationIsClickable({
      value: row[colIndex],
      column: cols[colIndex],
      settings,
    } as any),
  );
}

/** Dispara o clique do Metabase (filtro cruzado, link etc.) para a célula (linha, coluna) dada. */
export function clica(
  props: VisualizationProps,
  rowIndex: number,
  colIndex: number,
  evento: MouseEvent,
) {
  if (!clicavel(props, rowIndex, colIndex)) {
    return;
  }
  const { rows, cols } = props.series[0].data;
  const row = rows[rowIndex];
  props.onVisualizationClick?.({
    value: row[colIndex],
    column: cols[colIndex],
    data: row.map((value: any, i: number) => ({ value, col: cols[i] })),
    origin: { row, rowIndex, cols },
    settings: props.settings,
    event: evento.nativeEvent,
  } as any);
}

export const ESTILO_RAIZ: CSSProperties = {
  width: "100%",
  height: "100%",
  boxSizing: "border-box",
  overflow: "auto",
  padding: "10px 12px",
  color: "var(--mb-color-text-primary)",
  containerType: "size",
  fontFamily: "inherit",
} as CSSProperties;

export function SemDados({ texto = "Sem dados no período escolhido." }: { texto?: string }) {
  return (
    <div
      style={{
        ...ESTILO_RAIZ,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--mb-color-text-secondary)",
        fontSize: 14,
        textAlign: "center",
      }}
    >
      {texto}
    </div>
  );
}

export function Moldura({ children }: { children: ReactNode }) {
  return <div style={ESTILO_RAIZ}>{children}</div>;
}

/** Monta a definição padrão de uma visualização ALL. */
export function definicao(
  parcial: Pick<VisualizationDefinition, "identifier" | "iconName"> & {
    nome: string;
    largura: number;
    altura: number;
    settings?: VisualizationDefinition["settings"];
  },
): VisualizationDefinition {
  return {
    getUiName: () => parcial.nome,
    identifier: parcial.identifier,
    iconName: parcial.iconName,
    minSize: { width: Math.max(2, Math.floor(parcial.largura / 3)), height: 2 },
    defaultSize: { width: parcial.largura, height: parcial.altura },
    // Não sugeridas automaticamente: o autor da pergunta escolhe em "Visualizações personalizadas".
    isSensible: () => false,
    checkRenderable: () => undefined,
    // column_settings precisa estar declarado: é nele que o painel guarda o clique ("Ao clicar") de cada
    // coluna e a formatação; sem a declaração o Metabase não repassa esses ajustes para a visualização.
    settings: {
      ...columnSettings(),
      ...(parcial.settings ?? {}),
    },
  };
}
