/**
 * ALL · Galeria de telas — miniaturas de imagens (ex.: telas capturadas).
 * Clicar numa miniatura abre a imagem grande numa janela sobre a página, com ‹ › (e setas do teclado)
 * para passar pelas outras imagens do card. Ctrl/botão do meio na miniatura abre em nova aba, como link comum.
 *
 * Colunas:
 *   "Tela" / "URL" / "Imagem" ... endereço da imagem (ou a 1ª coluna marcada como URL)
 *   "Quando" ..................... (opcional) data e hora, mostrada na legenda
 *   "Colaborador" ................ (opcional) legenda
 *   "Programa ou site" ........... (opcional) legenda
 * Se a imagem não carregar, o cartão mostra "Imagem indisponível" e continua abrindo a janela.
 */
import {
  type CSSProperties,
  type MouseEvent,
  useCallback,
  useEffect,
  useState,
} from "react";
import { createPortal } from "react-dom";

import type { VisualizationProps } from "metabase/visualizations/types";
import { formatValue } from "metabase/visualizations/lib/formatting";

import {
  AZUL,
  ESTILO_RAIZ,
  SemDados,
  achaColuna,
  dadosDe,
  dataHora,
  definicao,
} from "./shared";

const DEFINICAO = definicao({
  identifier: "custom:all-galeria",
  iconName: "table",
  nome: "ALL · Galeria de telas",
  largura: 24,
  altura: 9,
});

type Tela = {
  url: string;
  pessoa: string;
  quando: string;
  programa: string;
};

export function AllGaleria(props: VisualizationProps) {
  const { rows, cols } = dadosDe(props);
  const [aberta, setAberta] = useState<number | null>(null);

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

  const telas: Tela[] = rows.map((r) => ({
    url: String(r[iUrl] ?? ""),
    pessoa: texto(r, iPessoa),
    quando: (iQuando >= 0 && dataHora(r[iQuando])) || texto(r, iQuando),
    programa: texto(r, iProg),
  }));

  return (
    <div style={ESTILO_RAIZ}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))",
          gap: 12,
        }}
      >
        {telas.map((t, i) => (
          <Miniatura key={i} tela={t} onAbrir={() => setAberta(i)} />
        ))}
      </div>
      {aberta != null && aberta < telas.length && (
        <JanelaDaTela
          telas={telas}
          indice={aberta}
          onMudar={setAberta}
          onFechar={() => setAberta(null)}
        />
      )}
    </div>
  );
}

function Miniatura({ tela, onAbrir }: { tela: Tela; onAbrir: () => void }) {
  const [falhou, setFalhou] = useState(false);
  const subtitulo = [tela.quando, tela.programa].filter(Boolean).join(" · ");
  const clique = (e: MouseEvent) => {
    // Clique comum abre a janela; Ctrl/Cmd/Shift/botão do meio seguem o link (nova aba).
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) {
      e.stopPropagation();
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    onAbrir();
  };
  return (
    <a
      href={tela.url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={clique}
      title="Ampliar"
      style={{
        display: "flex",
        flexDirection: "column",
        borderRadius: 10,
        overflow: "hidden",
        border: "1px solid var(--mb-color-border)",
        background: "var(--mb-color-background-secondary)",
        color: "inherit",
        textDecoration: "none",
        cursor: "zoom-in",
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
        {tela.url && !falhou ? (
          <img
            src={tela.url}
            alt={tela.pessoa || "Tela capturada"}
            loading="lazy"
            decoding="async"
            onError={() => setFalhou(true)}
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
          />
        ) : (
          <span style={{ color: "var(--mb-color-text-secondary)", fontSize: 13 }}>
            Imagem indisponível
          </span>
        )}
      </div>
      <div style={{ padding: "8px 10px" }}>
        {tela.pessoa && <div style={{ fontWeight: 700, fontSize: 13 }}>{tela.pessoa}</div>}
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

/* Janela sobre a página (sempre escura, padrão ALL). */
const FUNDO = "rgba(6, 11, 22, 0.94)";
const TEXTO = "#e8edf5";
const TEXTO_FRACO = "#9aa6b8";

const BOTAO: CSSProperties = {
  position: "absolute",
  top: "50%",
  transform: "translateY(-50%)",
  width: 48,
  height: 48,
  borderRadius: "50%",
  border: "1px solid rgba(255,255,255,0.15)",
  background: "rgba(18, 26, 43, 0.85)",
  color: TEXTO,
  fontSize: 30,
  lineHeight: "44px",
  textAlign: "center",
  cursor: "pointer",
  padding: 0,
  zIndex: 2,
};

function JanelaDaTela({
  telas,
  indice,
  onMudar,
  onFechar,
}: {
  telas: Tela[];
  indice: number;
  onMudar: (i: number) => void;
  onFechar: () => void;
}) {
  const total = telas.length;
  const tela = telas[indice];
  // Guardados por endereço: mudar de tela (ou o painel atualizar) não deixa estado velho.
  const [carregada, setCarregada] = useState<string | null>(null);
  const [comErro, setComErro] = useState<string | null>(null);
  const falhou = comErro === tela.url;
  const carregando = !falhou && carregada !== tela.url;
  const urlAnterior = indice > 0 ? telas[indice - 1].url : "";
  const urlProxima = indice < total - 1 ? telas[indice + 1].url : "";

  const anterior = useCallback(() => {
    if (indice > 0) {
      onMudar(indice - 1);
    }
  }, [indice, onMudar]);
  const proxima = useCallback(() => {
    if (indice < total - 1) {
      onMudar(indice + 1);
    }
  }, [indice, total, onMudar]);

  useEffect(() => {
    // Pré-carrega só as vizinhas (as imagens são grandes).
    [urlAnterior, urlProxima].forEach((url) => {
      if (url) {
        const img = new Image();
        img.src = url;
      }
    });
  }, [urlAnterior, urlProxima]);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      let tratada = true;
      if (e.key === "Escape") {
        onFechar();
      } else if (e.key === "ArrowLeft") {
        anterior();
      } else if (e.key === "ArrowRight") {
        proxima();
      } else {
        tratada = false;
      }
      if (tratada) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("keydown", tecla, true);
    const overflowAntes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", tecla, true);
      document.body.style.overflow = overflowAntes;
    };
  }, [anterior, proxima, onFechar]);

  const legenda = [tela.pessoa, tela.quando, tela.programa].filter(Boolean).join(" · ");
  const pare = (e: MouseEvent) => e.stopPropagation();

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Tela capturada"
      onClick={(e) => {
        e.stopPropagation();
        onFechar();
      }}
      onMouseDown={pare}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
        background: FUNDO,
        color: TEXTO,
        display: "flex",
        flexDirection: "column",
        fontFamily: "inherit",
      }}
    >
      {/* Topo: legenda, posição, abrir em nova aba e fechar */}
      <div
        onClick={pare}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "12px 16px",
          borderBottom: `2px solid ${AZUL}`,
          background: "rgba(18, 26, 43, 0.9)",
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            title={legenda}
            style={{
              fontWeight: 700,
              fontSize: 15,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {legenda || "Tela capturada"}
          </div>
          <div style={{ fontSize: 12, color: TEXTO_FRACO, marginTop: 2 }}>
            {indice + 1} de {total}
            {tela.url && (
              <>
                {" · "}
                <a
                  href={tela.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: TEXTO_FRACO, textDecoration: "underline" }}
                >
                  abrir em nova aba
                </a>
              </>
            )}
          </div>
        </div>
        <button
          type="button"
          aria-label="Fechar"
          title="Fechar (Esc)"
          onClick={onFechar}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            border: "1px solid rgba(255,255,255,0.15)",
            background: "transparent",
            color: TEXTO,
            fontSize: 22,
            lineHeight: "32px",
            cursor: "pointer",
            padding: 0,
            flexShrink: 0,
          }}
        >
          ×
        </button>
      </div>

      {/* Imagem; clicar fora dela fecha */}
      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "16px 72px",
        }}
      >
        {indice > 0 && (
          <button
            type="button"
            aria-label="Tela anterior"
            title="Anterior (←)"
            onClick={(e) => {
              e.stopPropagation();
              anterior();
            }}
            style={{ ...BOTAO, left: 12 }}
          >
            ‹
          </button>
        )}
        {tela.url && !falhou ? (
          <img
            key={tela.url}
            src={tela.url}
            alt={legenda || "Tela capturada"}
            onClick={pare}
            onLoad={() => setCarregada(tela.url)}
            onError={() => setComErro(tela.url)}
            style={{
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: "contain",
              borderRadius: 6,
              boxShadow: "0 10px 40px rgba(0,0,0,0.6)",
              opacity: carregando ? 0.35 : 1,
              transition: "opacity 120ms",
              cursor: "default",
            }}
          />
        ) : (
          <div onClick={pare} style={{ color: TEXTO_FRACO, textAlign: "center" }}>
            Não foi possível carregar esta imagem.
            {tela.url && (
              <div style={{ marginTop: 8 }}>
                <a
                  href={tela.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: AZUL }}
                >
                  Tentar abrir em nova aba
                </a>
              </div>
            )}
          </div>
        )}
        {carregando && (
          <div
            style={{
              position: "absolute",
              color: TEXTO_FRACO,
              fontSize: 13,
              pointerEvents: "none",
            }}
          >
            Carregando…
          </div>
        )}
        {indice < total - 1 && (
          <button
            type="button"
            aria-label="Próxima tela"
            title="Próxima (→)"
            onClick={(e) => {
              e.stopPropagation();
              proxima();
            }}
            style={{ ...BOTAO, right: 12 }}
          >
            ›
          </button>
        )}
      </div>
    </div>,
    document.body,
  );
}

Object.assign(AllGaleria, DEFINICAO);
