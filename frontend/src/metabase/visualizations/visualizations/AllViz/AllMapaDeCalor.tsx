/**
 * ALL · Mapa de calor — linhas × colunas, cada quadrado colorido pelo valor. Quem destoa aparece de relance.
 *
 * Colunas:
 *   1ª coluna ............ nome da linha (ex.: colaborador). Clicar no nome usa o clique configurado nessa coluna.
 *   colunas numéricas .... os quadrados; o cabeçalho é o nome da coluna (ex.: Seg, Ter, Qua...)
 *   colunas de texto ..... (opcionais, depois da 1ª) aparecem à direita, como informação extra
 * Ajustes: "Verde a partir de" (padrão 60), "Amarelo abaixo de" (padrão 40), "Sufixo" (padrão "%").
 * Entre os dois limites o quadrado fica cinza; valor vazio fica tracejado.
 */
import type { VisualizationProps } from "metabase/visualizations/types";

import {
  AMARELO,
  CINZA,
  ESTILO_RAIZ,
  SemDados,
  VERDE,
  clica,
  clicavel,
  colunaNumerica,
  dadosDe,
  definicao,
  ehNumero,
  formataNumero,
} from "./shared";

const DEFINICAO = definicao({
  identifier: "custom:all-mapa-de-calor",
  iconName: "calendar",
  nome: "ALL · Mapa de calor",
  largura: 24,
  altura: 8,
  settings: {
    "all.verde_a_partir_de": {
      getSection: () => "Exibição",
      title: "Verde a partir de",
      widget: "number",
      getDefault: () => 60,
    },
    "all.amarelo_abaixo_de": {
      getSection: () => "Exibição",
      title: "Amarelo abaixo de",
      widget: "number",
      getDefault: () => 40,
    },
    "all.sufixo": {
      getSection: () => "Exibição",
      title: "Sufixo",
      widget: "input",
      getDefault: () => "%",
    },
  },
});

export function AllMapaDeCalor(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  if (!rows.length || cols.length < 2) {
    return <SemDados />;
  }
  const verde = Number(props.settings["all.verde_a_partir_de"] ?? 60);
  const amarelo = Number(props.settings["all.amarelo_abaixo_de"] ?? 40);
  const sufixo = String(props.settings["all.sufixo"] ?? "%");
  const celulas: number[] = [];
  const extras: number[] = [];
  cols.forEach((_c, i) => {
    if (i === 0) {
      return;
    }
    (colunaNumerica(cols, rows, i) ? celulas : extras).push(i);
  });

  const corDaCelula = (v: number) =>
    v >= verde ? VERDE : v < amarelo ? AMARELO : CINZA;

  const grade = `minmax(110px, 1.6fr) repeat(${celulas.length}, minmax(40px, 1fr))${
    extras.length ? ` repeat(${extras.length}, minmax(80px, auto))` : ""
  }`;
  const cabecalho = {
    fontSize: 12,
    fontWeight: 700,
    color: "var(--mb-color-text-secondary)",
    textAlign: "center" as const,
    paddingBottom: 2,
  };

  return (
    <div style={ESTILO_RAIZ}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: grade,
          gap: 6,
          alignItems: "center",
          minWidth: 110 + celulas.length * 46 + extras.length * 86,
        }}
      >
        <div />
        {celulas.map((i) => (
          <div key={`h${i}`} style={cabecalho}>
            {cols[i].display_name}
          </div>
        ))}
        {extras.map((i) => (
          <div key={`h${i}`} style={{ ...cabecalho, textAlign: "right" }}>
            {cols[i].display_name}
          </div>
        ))}

        {rows.map((r, ri) => {
          const podeClicar = clicavel(props, ri, 0);
          return [
            <div
              key={`n${ri}`}
              onClick={(e) => clica(props, ri, 0, e)}
              title={String(r[0] ?? "")}
              style={{
                fontWeight: 600,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                cursor: podeClicar ? "pointer" : "default",
                color: podeClicar ? "var(--mb-color-brand)" : undefined,
              }}
            >
              {String(r[0] ?? "")}
            </div>,
            ...celulas.map((ci) => {
              const v = r[ci];
              if (!ehNumero(v)) {
                return (
                  <div
                    key={`c${ri}-${ci}`}
                    title={`${r[0]} · ${cols[ci].display_name}: sem uso`}
                    style={{
                      height: 34,
                      borderRadius: 8,
                      border: "1px dashed var(--mb-color-border)",
                      color: "var(--mb-color-text-tertiary)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 12,
                    }}
                  >
                    –
                  </div>
                );
              }
              const n = v as number;
              return (
                <div
                  key={`c${ri}-${ci}`}
                  title={`${r[0]} · ${cols[ci].display_name}: ${formataNumero(n)}${sufixo}`}
                  style={{
                    height: 34,
                    borderRadius: 8,
                    background: corDaCelula(n),
                    color: "#fff",
                    fontWeight: 700,
                    fontSize: 13,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {formataNumero(n, 0)}
                  {sufixo}
                </div>
              );
            }),
            ...extras.map((ci) => (
              <div
                key={`e${ri}-${ci}`}
                style={{
                  textAlign: "right",
                  color: "var(--mb-color-text-secondary)",
                  whiteSpace: "nowrap",
                  fontSize: 13,
                }}
              >
                {formataNumero(r[ci])}
              </div>
            )),
          ];
        })}
      </div>
      <div
        style={{
          display: "flex",
          gap: 16,
          flexWrap: "wrap",
          marginTop: 12,
          fontSize: 12,
          color: "var(--mb-color-text-secondary)",
        }}
      >
        <Legenda cor={VERDE} texto={`${verde}${sufixo} ou mais`} />
        <Legenda cor={CINZA} texto={`entre ${amarelo} e ${verde}${sufixo}`} />
        <Legenda cor={AMARELO} texto={`abaixo de ${amarelo}${sufixo}`} />
        <Legenda tracejado texto="sem uso" />
      </div>
    </div>
  );
}

function Legenda({
  cor,
  texto,
  tracejado,
}: {
  cor?: string;
  texto: string;
  tracejado?: boolean;
}) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 12,
          height: 12,
          borderRadius: 3,
          background: tracejado ? "transparent" : cor,
          border: tracejado ? "1px dashed var(--mb-color-border)" : "none",
        }}
      />
      {texto}
    </span>
  );
}

Object.assign(AllMapaDeCalor, DEFINICAO);
