export interface GameFolder {
  name: string;
  full_path: string;
  is_game: boolean;
  game_name: string;
  models: string[] | null;
  rounds_completed: number | null;
  rounds_total: number | null;
  created_timestamp: number | null;
}

export interface Agent {
  name: string;
  model_name: string | null;
  agent_class: string | null;
}

export interface RoundResults {
  winner?: string;
  scores: Record<string, number>;
  sorted_scores?: [string, number][];
  winner_percentage?: number | null;
  p_value?: number | null;
  player_stats?: Record<string, any>;
}

export interface Round {
  round_num: number;
  results: RoundResults;
}

export interface Message {
  role: string;
  content: string;
  [key: string]: any;
}

export interface Trajectory {
  player_name: string;
  round_num: number;
  api_calls: number;
  cost: number;
  exit_status: string | null;
  submission: string | null;
  memory: string | null;
  messages: Message[];
  diff: string | null;
  incremental_diff: string | null;
  diff_by_files: Record<string, string> | null;
  incremental_diff_by_files: Record<string, string> | null;
  modified_files: Record<string, string> | null;
  valid_submission: boolean | null;
}

export interface GameData {
  metadata: any;
  agents: Agent[];
  rounds: Round[];
}

export interface LineCountData {
  all_files: string[];
  line_counts_by_round: Record<string, Record<number, Record<string, number>>>;
}

export interface SimWinsData {
  players: string[];
  rounds: number[];
  scores_by_player: Record<string, number[]>;
}
