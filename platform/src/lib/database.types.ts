// Hand-written stub with the minimum of `profiles` and `pieces`.
// Task 4 replaces it with the generated `supabase/database.types.ts`.

export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type PieceStatus =
  | "queued"
  | "generating"
  | "review"
  | "ready"
  | "approved"
  | "needs_photos"
  | "rejected"
  | "failed";

export type PieceKind =
  | "mesa"
  | "mesita"
  | "aparador"
  | "estanteria"
  | "cabecero"
  | "panel"
  | "sofa"
  | "sillon"
  | "silla"
  | "jarron"
  | "lampara"
  | "otro";

type ProfileRow = {
  id: string;
  email: string | null;
  is_admin: boolean;
  attribution: Json | null;
  plan: string | null;
  created_at: string;
};

type PieceRow = {
  id: string;
  user_id: string;
  name: string;
  kind: PieceKind;
  width_cm: number;
  height_cm: number;
  depth_cm: number;
  rectilinear: boolean | null;
  notes: string | null;
  status: PieceStatus;
  attempt: number;
  route: string | null;
  claimed_at: string | null;
  error: string | null;
  review_note: string | null;
  reject_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type Database = {
  public: {
    Tables: {
      profiles: {
        Row: ProfileRow;
        Insert: Partial<ProfileRow> & Pick<ProfileRow, "id">;
        Update: Partial<ProfileRow>;
        Relationships: [];
      };
      pieces: {
        Row: PieceRow;
        Insert: Partial<PieceRow> &
          Pick<PieceRow, "user_id" | "name" | "kind" | "width_cm" | "height_cm" | "depth_cm">;
        Update: Partial<PieceRow>;
        Relationships: [];
      };
    };
    Views: { [_ in never]: never };
    Functions: {
      credit_balance: { Args: { p_user: string }; Returns: number };
    };
    Enums: { piece_status: PieceStatus; piece_kind: PieceKind };
    CompositeTypes: { [_ in never]: never };
  };
};

export type Profile = ProfileRow;
export type Piece = PieceRow;
