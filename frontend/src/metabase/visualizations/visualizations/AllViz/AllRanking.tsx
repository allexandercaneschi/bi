/**
 * ALL · Ranking de barras — lista do maior para o menor, com barra proporcional e o valor escrito.
 *
 * Colunas:
 *   1ª coluna ............ rótulo (ex.: programa ou site)
 *   "Tipo" ............... (opcional) dá a cor (Produtivo verde, Neutro cinza, Fora do trabalho laranja...)
 *   1ª coluna numérica ... tamanho da barra
 *   "Tempo" .............. (opcional) texto mostrado à direita no lugar do número
 * Clicar numa linha usa o clique configurado na 1ª coluna.
 */
import type { VisualizationProps } from "metabase/visualizations/types";

import {
  AZUL,
  ESTILO_RAIZ,
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

const DEFINICAO = definicao({
  identifier: "custom:all-ranking",
  iconName: "list",
  nome: "ALL · Ranking de barras",
  largura: 12,
  altura: 8,
});

export function AllRanking(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  const iTipo = achaColuna(cols, ["Tipo", "Categoria"]);
  const iTexto = achaColuna(cols, ["Tempo", "Texto"]);
  const iValor = cols.findIndex(
    (_c, i) => i > 0 && i !== iTipo && i !== iTexto && colunaNumerica(cols, rows, i),
  );
  if (!rows.length || iValor < 0) {
    return <SemDados />;
  }
  const maximo = Math.max(...rows.map((r) => Number(r[iValor]) || 0), 0) || 1;
  const tipos = iTipo >= 0 ? Array.from(new Set(rows.map((r) => String(r[iTipo] ?? "")))) : [];

  return (
    <div style={{ ...ESTILO_RAIZ, display: "flex", flexDirection: "column", gap: 9 }}>
      {rows.map((r, ri) => {
        const cor = iTipo >= 0 ? corDe(r[iTipo], AZUL) : AZUL;
        const v = Number(r[iValor]) || 0;
        const podeClicar = clicavel(props, ri, 0);
        return (
          <div
            key={ri}
            onClick={(e) => clica(props, ri, 0, e)}
            title={`${r[0]}${iTipo >= 0 ? ` (${r[iTipo]})` : ""}`}
            style={{ cursor: podeClicar ? "pointer" : "default" }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 10,
                fontSize: 13,
                marginBottom: 3,
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 7,
                  minWidth: 0,
                  fontWeight: 600,
                }}
              >
                <span
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: "50%",
                    background: cor,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                >
                  {String(r[0] ?? "")}
                </span>
              </span>
              <span style={{ whiteSpace: "nowrap", color: "var(--mb-color-text-secondary)" }}>
                {iTexto >= 0 ? String(r[iTexto] ?? "") : formataNumero(v)}
              </span>
            </div>
            <div
              style={{
                height: 8,
                borderRadius: 4,
                background: "var(--mb-color-background-tertiary)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${Math.max(2, (100 * v) / maximo)}%`,
                  height: "100%",
                  borderRadius: 4,
                  background: cor,
                }}
              />
            </div>
          </div>
        );
      })}
      {tipos.length > 1 && (
        <div
          style={{
            display: "flex",
            gap: 14,
            flexWrap: "wrap",
            fontSize: 12,
            color: "var(--mb-color-text-secondary)",
            marginTop: 4,
          }}
        >
          {tipos.map((t) => (
            <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span
                style={{ width: 9, height: 9, borderRadius: "50%", background: corDe(t, AZUL) }}
              />
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

Object.assign(AllRanking, DEFINICAO);
