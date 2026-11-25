/**
 * ALL · Lista de avisos — frases curtas com um ícone de cor, do mais grave ao tudo certo.
 *
 * Colunas:
 *   1ª coluna de texto ... a frase
 *   "Nível" .............. (opcional) alerta | atencao | ok  (sem ela: "atencao")
 */
import type { VisualizationProps } from "metabase/visualizations/types";

import {
  AMARELO,
  ESTILO_RAIZ,
  LARANJA,
  SemDados,
  VERDE,
  achaColuna,
  dadosDe,
  definicao,
  semAcento,
} from "./shared";

const DEFINICAO = definicao({
  identifier: "custom:all-avisos",
  iconName: "warning",
  nome: "ALL · Lista de avisos",
  largura: 12,
  altura: 6,
});

const NIVEIS: Record<string, { cor: string; simbolo: string; ordem: number }> = {
  alerta: { cor: LARANJA, simbolo: "!", ordem: 0 },
  atencao: { cor: AMARELO, simbolo: "!", ordem: 1 },
  ok: { cor: VERDE, simbolo: "✓", ordem: 2 },
};

export function AllAvisos(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  const iNivel = achaColuna(cols, ["Nível", "Nivel"]);
  let iMsg = cols.findIndex((_c, i) => i !== iNivel);
  if (iMsg < 0) {
    iMsg = 0;
  }
  const itens = rows
    .map((r, i) => {
      const chave = iNivel >= 0 ? semAcento(r[iNivel]) : "atencao";
      return { i, texto: String(r[iMsg] ?? ""), nivel: NIVEIS[chave] ?? NIVEIS.atencao };
    })
    .filter((x) => x.texto)
    .sort((a, b) => a.nivel.ordem - b.nivel.ordem || a.i - b.i);
  if (!itens.length) {
    return <SemDados texto="Nada fora do normal." />;
  }
  return (
    <div style={{ ...ESTILO_RAIZ, display: "flex", flexDirection: "column", gap: 8 }}>
      {itens.map((x) => (
        <div
          key={x.i}
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            padding: "10px 12px",
            borderRadius: 10,
            background: "var(--mb-color-background-secondary)",
            borderLeft: `4px solid ${x.nivel.cor}`,
          }}
        >
          <span
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              background: x.nivel.cor,
              color: "#fff",
              fontWeight: 800,
              fontSize: 13,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {x.nivel.simbolo}
          </span>
          <span style={{ lineHeight: 1.4 }}>{x.texto}</span>
        </div>
      ))}
    </div>
  );
}

Object.assign(AllAvisos, DEFINICAO);
