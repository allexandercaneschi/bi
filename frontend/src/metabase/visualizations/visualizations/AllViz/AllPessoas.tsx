/**
 * ALL · Cartões de pessoas — um cartão por pessoa (ou computador), com iniciais, tempo e situação.
 *
 * Colunas (todas opcionais, menos a 1ª):
 *   1ª coluna ou "Colaborador" ........ nome. Clicar no cartão usa o clique configurado nessa coluna
 *                                        (ex.: filtro cruzado do painel).
 *   "Tempo" / "Tempo por dia" ......... número grande do cartão
 *   "Dias de uso" ..................... texto pequeno ao lado do tempo
 *   "Produtivo (%)", "Neutro (%)",
 *   "Fora do trabalho (%)" ............ mini barra colorida (neutro = 100 - os outros, se faltar)
 *   "Situação" ........................ etiqueta colorida (Em uso, Sem contato hoje...)
 *   "Computador" ...................... texto abaixo do nome
 *   "Último uso" / "Último contato" ... texto no rodapé
 */
import type { VisualizationProps } from "metabase/visualizations/types";
import { formatValue } from "metabase/visualizations/lib/formatting";

import {
  CINZA,
  ESTILO_RAIZ,
  LARANJA,
  SemDados,
  VERDE,
  achaColuna,
  clica,
  clicavel,
  corDaSituacao,
  corDoNome,
  dadosDe,
  definicao,
  ehNumero,
  iniciais,
} from "./shared";

const DEFINICAO = definicao({
  identifier: "custom:all-pessoas",
  iconName: "person",
  nome: "ALL · Cartões de pessoas",
  largura: 24,
  altura: 7,
});

function num(v: unknown): number | null {
  return ehNumero(v) ? (v as number) : null;
}

export function AllPessoas(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  if (!rows.length) {
    return <SemDados />;
  }
  let iNome = achaColuna(cols, ["Colaborador", "Nome", "Pessoa"]);
  if (iNome < 0) {
    iNome = 0;
  }
  const iTempo = achaColuna(cols, ["Tempo", "Tempo por dia", "Tempo trabalhando"]);
  const iDias = achaColuna(cols, ["Dias de uso", "Dias"]);
  const iProd = achaColuna(cols, ["Produtivo (%)", "Produtivo"]);
  const iNeutro = achaColuna(cols, ["Neutro (%)", "Neutro"]);
  const iFora = achaColuna(cols, ["Fora do trabalho (%)", "Fora do trabalho"]);
  const iSit = achaColuna(cols, ["Situação", "Situacao", "Status"]);
  const iPc = achaColuna(cols, ["Computador", "Dispositivo"]);
  const iUltimo = achaColuna(cols, ["Último uso", "Ultimo uso", "Último contato", "Ultimo contato"]);

  const formata = (v: unknown, ci: number) =>
    v == null
      ? ""
      : String(
          formatValue(v as any, {
            column: cols[ci],
            jsx: false,
          } as any) ?? "",
        );

  return (
    <div style={ESTILO_RAIZ}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))",
          gap: 10,
        }}
      >
        {rows.map((r, ri) => {
          const nome = String(r[iNome] ?? "");
          const prod = iProd >= 0 ? num(r[iProd]) : null;
          const fora = iFora >= 0 ? num(r[iFora]) : null;
          let neutro = iNeutro >= 0 ? num(r[iNeutro]) : null;
          if (neutro == null && (prod != null || fora != null)) {
            neutro = Math.max(0, 100 - (prod ?? 0) - (fora ?? 0));
          }
          const temBarra = prod != null || fora != null || neutro != null;
          const situacao = iSit >= 0 ? String(r[iSit] ?? "") : "";
          const podeClicar = clicavel(props, ri, iNome);
          return (
            <div
              key={ri}
              onClick={(e) => clica(props, ri, iNome, e)}
              style={{
                border: "1px solid var(--mb-color-border)",
                borderRadius: 12,
                padding: "12px 14px",
                background: "var(--mb-color-background-secondary)",
                cursor: podeClicar ? "pointer" : "default",
                display: "flex",
                flexDirection: "column",
                gap: 8,
                minWidth: 0,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "50%",
                    background: corDoNome(nome),
                    color: "#fff",
                    fontWeight: 700,
                    fontSize: 14,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {iniciais(nome)}
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div
                    title={nome}
                    style={{
                      fontWeight: 700,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {nome}
                  </div>
                  {iPc >= 0 && r[iPc] != null && (
                    <div style={{ fontSize: 12, color: "var(--mb-color-text-secondary)" }}>
                      {String(r[iPc])}
                    </div>
                  )}
                </div>
                {situacao && (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "#fff",
                      background: corDaSituacao(situacao),
                      borderRadius: 999,
                      padding: "3px 8px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {situacao}
                  </span>
                )}
              </div>

              {iTempo >= 0 && (
                <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                  <span style={{ fontSize: 22, fontWeight: 800 }}>
                    {formata(r[iTempo], iTempo)}
                  </span>
                  <span style={{ fontSize: 12, color: "var(--mb-color-text-secondary)" }}>
                    {cols[iTempo].display_name.toLowerCase().includes("dia") ? "por dia" : ""}
                    {iDias >= 0 && r[iDias] != null
                      ? ` · ${r[iDias]} ${Number(r[iDias]) === 1 ? "dia" : "dias"}`
                      : ""}
                  </span>
                </div>
              )}

              {temBarra && (
                <div>
                  <div
                    style={{
                      display: "flex",
                      height: 8,
                      borderRadius: 4,
                      overflow: "hidden",
                      background: "var(--mb-color-background-tertiary)",
                    }}
                  >
                    <div style={{ width: `${prod ?? 0}%`, background: VERDE }} />
                    <div style={{ width: `${neutro ?? 0}%`, background: CINZA }} />
                    <div style={{ width: `${fora ?? 0}%`, background: LARANJA }} />
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      marginTop: 4,
                      color: "var(--mb-color-text-secondary)",
                    }}
                  >
                    <span style={{ color: VERDE, fontWeight: 700 }}>
                      {prod != null ? `${Math.round(prod)}% produtivo` : ""}
                    </span>
                    <span style={{ color: (fora ?? 0) >= 25 ? LARANJA : undefined, fontWeight: 600 }}>
                      {fora != null ? `${Math.round(fora)}% fora do trabalho` : ""}
                    </span>
                  </div>
                </div>
              )}

              {iUltimo >= 0 && r[iUltimo] != null && (
                <div style={{ fontSize: 11, color: "var(--mb-color-text-tertiary)" }}>
                  {cols[iUltimo].display_name}: {formata(r[iUltimo], iUltimo)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(AllPessoas, DEFINICAO);
