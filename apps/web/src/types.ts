export type Dict = Record<string, any>;
export type View =
  | "Mission room"
  | "Step graph"
  | "Council round"
  | "Conflict map"
  | "Experiment board"
  | "Evidence"
  | "Bottleneck map"
  | "Decision ledger"
  | "Research report";
export interface ResearchView {
  mission: Dict;
  steps: Dict[];
  rounds: Dict[];
  concerns: Dict[];
  hypotheses: Dict[];
  experiments: Dict[];
  evidences: Dict[];
  decisions: Dict[];
  tradeoffs: Dict[];
  reframes: Dict[];
  causal_edges: Dict[];
  causal_nodes: Dict[];
  challenge_groups: Dict[];
  artifacts: Dict[];
  calls: Dict[];
  jobs: Dict[];
  events: Dict[];
  budget: Dict;
}
