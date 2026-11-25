/**
 * ALL · Barra de proporção — uma barra só, dividida entre categorias, com legenda clara.
 *
 * Colunas (uma linha por categoria):
 *   1ª coluna ............ nome da categoria ("Produtivo", "Neutro", "Fora do trabalho"...)
 *   1ª coluna numérica ... valor (ex.: horas)
 *   "Cor" ................ (opcional) cor da categoria; sem ela, a cor sai do nome
 *                           (Produtivo verde, Neutro cinza, Fora do trabalho laranja, Parado)
 * Ajuste: "Unidade" (padrão "h") aparece depois do valor na legenda.
 */
import type { VisualizationProps } from "metabase/visualizations/types";

import {
  AZUL,
  AMARELO,
  ESTILO_RAIZ,
  ROXO,
  SemDados,
  achaColuna,
  clica,
  clicavel,
  colunaNumerica,
  corDe,
  dadosDe,
  definicao,
  formataNumero,
} from "./shared";

const RESERVA = [AZUL, ROXO, AMARELO, "#3fb7b0", "#e0508a"];

const DEFINICAO = definicao({
  identifier: "custom:all-proporcao",
  iconName: "progress",
  nome: "ALL · Barra de proporção",
  largura: 12,
  altura: 4,
  settings: {
    "all.unidade": {
      getSection: () => "Exibição",
      title: "Unidade",
      widget: "input",
      getDefault: () => "h",
    },
  },
});

export function AllProporcao(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  const iValor = cols.findIndex((_c, i) => i > 0 && colunaNumerica(cols, rows, i));
  if (!rows.length || iValor < 0) {
    return <SemDados />;
  }
  const iCor = achaColuna(cols, ["Cor"]);
  const unidade = String(props.settings["all.unidade"] ?? "h");
  const itens = rows
    .map((r, i) => ({
      i,
      nome: String(r[0] ?? ""),
      valor: Math.max(0, Number(r[iValor]) || 0),
      cor: corDe(iCor >= 0 ? r[iCor] : r[0], RESERVA[i % RESERVA.length]),
    }))
    .filter((x) => x.valor > 0);
  const total = itens.reduce((s, x) => s + x.valor, 0);
  if (total <= 0) {
    return <SemDados />;
  }

  return (
    <div
      style={{
        ...ESTILO_RAIZ,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 14,
      }}
    >
      <div
        style={{
          display: "flex",
          height: "clamp(28px, 22cqh, 44px)",
          borderRadius: 10,
          overflow: "hidden",
          background: "var(--mb-color-background-tertiary)",
        }}
      >
        {itens.map((x) => {
          const pct = (100 * x.valor) / total;
          const podeClicar = clicavel(props, x.i, 0);
          return (
            <div
              key={x.i}
              title={`${x.nome}: ${formataNumero(x.valor)} ${unidade} (${Math.round(pct)}%)`}
              onClick={(e) => clica(props, x.i, 0, e)}
              style={{
                width: `${pct}%`,
                background: x.cor,
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
                fontSize: 14,
                cursor: podeClicar ? "pointer" : "default",
                borderRight: "2px solid var(--mb-color-background-primary)",
              }}
            >
              {pct >= 9 ? `${Math.round(pct)}%` : ""}
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 22px" }}>
        {itens.map((x) => (
          <div key={x.i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: 3,
                background: x.cor,
                flexShrink: 0,
              }}
            />
            <span style={{ fontWeight: 600 }}>{x.nome}</span>
            <span style={{ color: "var(--mb-color-text-secondary)" }}>
              {formataNumero(x.valor)} {unidade} · {Math.round((100 * x.valor) / total)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(AllProporcao, DEFINICAO);
