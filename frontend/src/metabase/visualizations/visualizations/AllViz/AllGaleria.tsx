/**
 * ALL · Galeria de telas — miniaturas de imagens (ex.: telas capturadas); clicar abre a imagem.
 *
 * Colunas:
 *   "Tela" / "URL" / "Imagem" ... endereço da imagem (ou a 1ª coluna marcada como URL)
 *   "Quando" ..................... (opcional) data e hora, mostrada na legenda
 *   "Colaborador" ................ (opcional) legenda
 *   "Programa ou site" ........... (opcional) legenda
 * Se a imagem não carregar, o cartão mostra "Abrir tela" com o link.
 */
import { useState } from "react";

import type { VisualizationProps } from "metabase/visualizations/types";
import { formatValue } from "metabase/visualizations/lib/formatting";

import {
  ESTILO_RAIZ,
  SemDados,
  achaColuna,
  dadosDe,
  definicao,
} from "./shared";

const DEFINICAO = definicao({
  identifier: "custom:all-galeria",
  iconName: "table",
  nome: "ALL · Galeria de telas",
  largura: 24,
  altura: 9,
});

export function AllGaleria(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  let iUrl = achaColuna(cols, ["Tela", "URL", "Imagem", "Link"]);
  if (iUrl < 0) {
    iUrl = cols.findIndex((c) => String(c.semantic_type ?? "").includes("URL"));
  }
  if (!rows.length || iUrl < 0) {
    return <SemDados texto="Nenhuma tela capturada no período escolhido." />;
  }
  const iQuando = achaColuna(cols, ["Quando", "Capturado em", "Data"]);
  const iPessoa = achaColuna(cols, ["Colaborador"]);
  const iProg = achaColuna(cols, ["Programa ou site", "Programa", "Título", "Titulo"]);
  const texto = (r: any[], i: number) =>
    i < 0 || r[i] == null
      ? ""
      : String(formatValue(r[i], { column: cols[i], jsx: false } as any) ?? "");

  return (
    <div style={ESTILO_RAIZ}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))",
          gap: 12,
        }}
      >
        {rows.map((r, ri) => (
          <Miniatura
            key={ri}
            url={String(r[iUrl] ?? "")}
            titulo={texto(r, iPessoa)}
            subtitulo={[texto(r, iQuando), texto(r, iProg)].filter(Boolean).join(" · ")}
          />
        ))}
      </div>
    </div>
  );
}

function Miniatura({
  url,
  titulo,
  subtitulo,
}: {
  url: string;
  titulo: string;
  subtitulo: string;
}) {
  const [falhou, setFalhou] = useState(false);
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "flex",
        flexDirection: "column",
        borderRadius: 10,
        overflow: "hidden",
        border: "1px solid var(--mb-color-border)",
        background: "var(--mb-color-background-secondary)",
        color: "inherit",
        textDecoration: "none",
      }}
    >
      <div
        style={{
          aspectRatio: "16 / 9",
          background: "var(--mb-color-background-tertiary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {url && !falhou ? (
          <img
            src={url}
            alt={titulo || "Tela capturada"}
            loading="lazy"
            onError={() => setFalhou(true)}
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
          />
        ) : (
          <span style={{ color: "var(--mb-color-brand)", fontWeight: 700 }}>Abrir tela</span>
        )}
      </div>
      <div style={{ padding: "8px 10px" }}>
        {titulo && <div style={{ fontWeight: 700, fontSize: 13 }}>{titulo}</div>}
        {subtitulo && (
          <div
            title={subtitulo}
            style={{
              fontSize: 12,
              color: "var(--mb-color-text-secondary)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {subtitulo}
          </div>
        )}
      </div>
    </a>
  );
}

Object.assign(AllGaleria, DEFINICAO);
