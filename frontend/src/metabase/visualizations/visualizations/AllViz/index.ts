/**
 * ALL Tecnologias: visualizações próprias do ALL B.I (registradas em visualizations/register.js).
 * Ficam no seletor de visualização de qualquer pergunta, em "Visualizações personalizadas".
 * O contrato de colunas de cada uma está no topo do arquivo dela e em ALL-FORK.md.
 */
import type { Visualization } from "metabase/visualizations/types/visualization";

import { AllAvisos } from "./AllAvisos";
import { AllGaleria } from "./AllGaleria";
import { AllIndicador } from "./AllIndicador";
import { AllLinhaDoTempo } from "./AllLinhaDoTempo";
import { AllMapaDeCalor } from "./AllMapaDeCalor";
import { AllPessoas } from "./AllPessoas";
import { AllProporcao } from "./AllProporcao";
import { AllRanking } from "./AllRanking";

export const ALL_VISUALIZATIONS = [
  AllIndicador,
  AllProporcao,
  AllMapaDeCalor,
  AllLinhaDoTempo,
  AllPessoas,
  AllAvisos,
  AllRanking,
  AllGaleria,
] as unknown as Visualization[];

/** Identificadores ("custom:all-...") das visualizações ALL, para quem precisa reconhecê-las. */
export const isAllVisualization = (display: unknown): boolean =>
  typeof display === "string" && display.startsWith("custom:all-");
