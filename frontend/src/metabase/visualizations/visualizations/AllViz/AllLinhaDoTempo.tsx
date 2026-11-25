/**
 * ALL · Linha do tempo do dia — em que horas o computador foi usado e como.
 *
 * Colunas (uma linha por hora e tipo):
 *   "Hora" ....... hora do dia: número (8) ou texto ("08h")
 *   "Tipo" ....... (opcional) Produtivo | Neutro | Fora do trabalho | Parado | outro (vira cor da paleta)
 *   "Horas" ...... quanto tempo naquela hora (ou a 1ª coluna numérica que não seja a hora)
 * As horas vazias entre a primeira e a última aparecem como espaço (ex.: almoço).
 */
import type { VisualizationProps } from "metabase/visualizations/types";

import {
  AZUL,
  ESTILO_RAIZ,
  SemDados,
  achaColuna,
  colunaNumerica,
  corDe,
  dadosDe,
  definicao,
  formataNumero,
} from "./shared";

const DEFINICAO = definicao({
  identifier: "custom:all-linha-do-tempo",
  iconName: "bar",
  nome: "ALL · Linha do tempo do dia",
  largura: 24,
  altura: 6,
});

const ORDEM_TIPOS = ["produtivo", "neutro", "fora do trabalho", "parado"];

function horaDe(v: unknown): number | null {
  const n = typeof v === "number" ? v : parseInt(String(v ?? ""), 10);
  return Number.isFinite(n) && n >= 0 && n <= 23 ? n : null;
}

export function AllLinhaDoTempo(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  let iHora = achaColuna(cols, ["Hora"]);
  if (iHora < 0) {
    iHora = 0;
  }
  const iTipo = achaColuna(cols, ["Tipo"]);
  let iValor = achaColuna(cols, ["Horas", "Minutos", "Valor"]);
  if (iValor < 0) {
    iValor = cols.findIndex((_c, i) => i !== iHora && colunaNumerica(cols, rows, i));
  }
  const pontos = rows
    .map((r) => ({
      hora: horaDe(r[iHora]),
      tipo: iTipo >= 0 ? String(r[iTipo] ?? "") : "Uso",
      valor: Math.max(0, Number(r[iValor]) || 0),
    }))
    .filter((p) => p.hora != null && p.valor > 0) as {
    hora: number;
    tipo: string;
    valor: number;
  }[];
  if (!pontos.length || iValor < 0) {
    return <SemDados />;
  }

  const tipos = Array.from(new Set(pontos.map((p) => p.tipo))).sort((a, b) => {
    const ia = ORDEM_TIPOS.indexOf(a.toLowerCase());
    const ib = ORDEM_TIPOS.indexOf(b.toLowerCase());
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  const inicio = Math.min(7, ...pontos.map((p) => p.hora));
  const fim = Math.max(18, ...pontos.map((p) => p.hora));
  const horas: number[] = [];
  for (let h = inicio; h <= fim; h++) {
    horas.push(h);
  }
  const porHora = new Map<number, Map<string, number>>();
  for (const p of pontos) {
    const m = porHora.get(p.hora) ?? new Map<string, number>();
    m.set(p.tipo, (m.get(p.tipo) ?? 0) + p.valor);
    porHora.set(p.hora, m);
  }
  const maximo = Math.max(
    ...horas.map((h) =>
      Array.from(porHora.get(h)?.values() ?? []).reduce((s, v) => s + v, 0),
    ),
  );
  const unidade = semAcentoMin(cols[iValor]?.display_name).startsWith("min") ? "min" : "h";

  return (
    <div
      style={{
        ...ESTILO_RAIZ,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div
        style={{
          flex: 1,
          minHeight: 80,
          display: "grid",
          gridTemplateColumns: `repeat(${horas.length}, 1fr)`,
          gap: 4,
          alignItems: "end",
          borderBottom: "1px solid var(--mb-color-border)",
          paddingBottom: 2,
        }}
      >
        {horas.map((h) => {
          const m = porHora.get(h);
          const total = Array.from(m?.values() ?? []).reduce((s, v) => s + v, 0);
          const detalhe = tipos
            .filter((t) => (m?.get(t) ?? 0) > 0)
            .map((t) => `${t}: ${formataNumero(m?.get(t))} ${unidade}`)
            .join("\n");
          return (
            <div
              key={h}
              title={total ? `${String(h).padStart(2, "0")}h\n${detalhe}` : `${String(h).padStart(2, "0")}h: sem uso`}
              style={{
                height: "100%",
                display: "flex",
                flexDirection: "column-reverse",
                borderRadius: 6,
                background: "var(--mb-color-background-tertiary)",
                overflow: "hidden",
              }}
            >
              {tipos.map((t) => {
                const v = m?.get(t) ?? 0;
                return v > 0 ? (
                  <div
                    key={t}
                    style={{
                      height: `${(100 * v) / (maximo || 1)}%`,
                      background: corDe(t, AZUL),
                      minHeight: 2,
                    }}
                  />
                ) : null;
              })}
            </div>
          );
        })}
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${horas.length}, 1fr)`,
          gap: 4,
          fontSize: 11,
          color: "var(--mb-color-text-secondary)",
          textAlign: "center",
        }}
      >
        {horas.map((h) => (
          <div key={h}>
            {horas.length > 14 && h % 2 ? "" : `${String(h).padStart(2, "0")}h`}
          </div>
        ))}
      </div>
      <div
        style={{
          display: "flex",
          gap: 16,
          flexWrap: "wrap",
          fontSize: 12,
          color: "var(--mb-color-text-secondary)",
        }}
      >
        {tipos.map((t) => (
          <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span
              style={{ width: 12, height: 12, borderRadius: 3, background: corDe(t, AZUL) }}
            />
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

function semAcentoMin(v: unknown) {
  return String(v ?? "").toLowerCase();
}

Object.assign(AllLinhaDoTempo, DEFINICAO);
