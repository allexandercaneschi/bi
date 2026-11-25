/**
 * ALL · Indicador — um número (ou uma frase curta) em destaque.
 *
 * Colunas (só a primeira linha é usada):
 *   1ª coluna ........ o valor ("6h 18min", 68, "Ana usou o computador...")
 *   "Rótulo" ......... (opcional) texto acima do valor; sem ele, usa o nome da 1ª coluna
 *   "Detalhe" ........ (opcional) frase curta abaixo do valor
 *   "Cor" ............ (opcional) verde | amarelo | laranja | cinza | azul | roxo | #hex
 *   "Sufixo" ......... (opcional) texto logo após o valor (ex.: "%")
 */
import type { VisualizationProps } from "metabase/visualizations/types";

import {
  AZUL,
  ESTILO_RAIZ,
  SemDados,
  achaColuna,
  corDe,
  dadosDe,
  definicao,
  formataNumero,
} from "./shared";

const DEFINICAO = definicao({
  identifier: "custom:all-indicador",
  iconName: "gauge",
  nome: "ALL · Indicador",
  largura: 6,
  altura: 3,
});

export function AllIndicador(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  if (!rows.length || !cols.length) {
    return <SemDados />;
  }
  const row = rows[0];
  const iRotulo = achaColuna(cols, ["Rótulo", "Rotulo"]);
  const iDetalhe = achaColuna(cols, ["Detalhe"]);
  const iCor = achaColuna(cols, ["Cor"]);
  const iSufixo = achaColuna(cols, ["Sufixo"]);

  const valor = formataNumero(row[0]) + (iSufixo >= 0 ? String(row[iSufixo] ?? "") : "");
  const rotulo = iRotulo >= 0 ? String(row[iRotulo] ?? "") : "";
  const detalhe = iDetalhe >= 0 ? String(row[iDetalhe] ?? "") : "";
  const cor = iCor >= 0 ? corDe(row[iCor], AZUL) : AZUL;
  const frase = valor.length > 24;

  return (
    <div
      style={{
        ...ESTILO_RAIZ,
        display: "flex",
        alignItems: "stretch",
        gap: 12,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: 6,
          borderRadius: 3,
          background: cor,
          flexShrink: 0,
        }}
      />
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          minWidth: 0,
          flex: 1,
        }}
      >
        {rotulo && (
          <div
            style={{
              fontSize: 13,
              color: "var(--mb-color-text-secondary)",
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
            {rotulo}
          </div>
        )}
        <div
          style={{
            fontSize: frase
              ? "clamp(15px, min(16cqh, 4.2cqw), 24px)"
              : "clamp(22px, min(30cqh, 14cqw), 56px)",
            fontWeight: frase ? 600 : 800,
            lineHeight: frase ? 1.35 : 1.05,
            letterSpacing: frase ? 0 : "-0.02em",
            overflowWrap: "anywhere",
          }}
        >
          {valor}
        </div>
        {detalhe && (
          <div
            style={{
              fontSize: 13,
              color: "var(--mb-color-text-secondary)",
              marginTop: 6,
              lineHeight: 1.35,
            }}
          >
            {detalhe}
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(AllIndicador, DEFINICAO);
