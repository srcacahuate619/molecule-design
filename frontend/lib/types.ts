export type ValidationResult = {
  is_valid: boolean;
  canonical_smiles: string | null;
  smiles_hash: string | null;
  errors: string[];
  warnings: string[];
  heavy_atom_count: number | null;
  molecular_formula: string | null;
};

export type EvaluationSubmitResponse = {
  task_id: string;
  status: string;
  target_pdb_id: string;
  smiles_hash: string;
};

export type DockingPose = {
  rank: number;
  affinity_kcal: number;
  rmsd_lb: number;
  rmsd_ub: number;
};

export type EvaluationResult = {
  id: string;
  molecule_id: string;

  // Docking
  affinity_kcal: number | null;
  affinity_score: number | null;
  docking_poses: DockingPose[] | null;
  parsing_source: string | null;
  vina_version: string | null;
  vina_random_seed: number | null;
  scientific_warnings: string[] | null;
  celery_task_id: string | null;

  // Properties
  molecular_weight: number | null;
  log_p: number | null;
  tpsa: number | null;
  hbd: number | null;
  hba: number | null;
  rotatable_bonds: number | null;
  heavy_atom_count: number | null;
  ring_count: number | null;
  lipinski_pass: boolean | null;
  veber_pass: boolean | null;
  qed: number | null;

  // Scores
  adme_score: number | null;
  druglikeness_score: number | null;
  total_score: number | null;

  // Files
  poses_file_path: string | null;

  // Report
  ai_report: string | null;

  // Blockchain
  blockchain_tx_id: string | null;

  error_message: string | null;
  evaluated_at: string;
};

export type JobStatus = {
  task_id: string;
  status: string;
  progress: number;
  result: EvaluationResult | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
};

// ── History Types ────────────────────────────────────────────────

export type EvaluationSummary = {
  molecule_id: string;
  smiles: string;
  name: string | null;
  status: string;
  target_pdb_id: string;
  total_score: number | null;
  affinity_kcal: number | null;
  affinity_score: number | null;
  adme_score: number | null;
  druglikeness_score: number | null;
  molecular_weight: number | null;
  log_p: number | null;
  lipinski_pass: boolean | null;
  qed: number | null;
  evaluated_at: string | null;
  created_at: string;
};

export type HistoryResponse = {
  items: EvaluationSummary[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
};

export type UserStats = {
  total_evaluations: number;
  completed_evaluations: number;
  failed_evaluations: number;
  best_score: number | null;
  avg_score: number | null;
  unique_targets: number;
};

// ── Suggestion Types ─────────────────────────────────────────────

export type MolecularSuggestion = {
  smiles: string;
  name: string;
  description: string;
  rationale: string;
  modification_type: string;
  expected_effect: string;
  confidence: string;
  source: string;
  warnings: string[];
};

export type SuggestionResponse = {
  success: boolean;
  suggestions: MolecularSuggestion[];
  method: string;
  warnings: string[];
  disclaimer: string;
};

// ── AlphaFold Types ──────────────────────────────────────────────

export type AlphaFoldEntry = {
  uniprot_id: string;
  gene: string | null;
  organism: string | null;
  model_url: string;
  mean_plddt: number | null;
  high_confidence_residues: number | null;
  total_residues: number | null;
  warnings: string[];
};
