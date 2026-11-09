export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  graphql_public: {
    Tables: {
      [_ in never]: never
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      graphql: {
        Args: {
          extensions?: Json
          operationName?: string
          query?: string
          variables?: Json
        }
        Returns: Json
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
  public: {
    Tables: {
      credit_ledger: {
        Row: {
          created_at: string
          delta: number
          id: string
          piece_id: string | null
          reason: Database["public"]["Enums"]["credit_reason"]
          stripe_session_id: string | null
          user_id: string
        }
        Insert: {
          created_at?: string
          delta: number
          id?: string
          piece_id?: string | null
          reason: Database["public"]["Enums"]["credit_reason"]
          stripe_session_id?: string | null
          user_id: string
        }
        Update: {
          created_at?: string
          delta?: number
          id?: string
          piece_id?: string | null
          reason?: Database["public"]["Enums"]["credit_reason"]
          stripe_session_id?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "credit_ledger_piece_id_fkey"
            columns: ["piece_id"]
            isOneToOne: false
            referencedRelation: "admin_review_queue"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "credit_ledger_piece_id_fkey"
            columns: ["piece_id"]
            isOneToOne: false
            referencedRelation: "pieces"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "credit_ledger_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      piece_models: {
        Row: {
          attempt: number
          candidate: number
          cost_usd: number | null
          created_at: string
          glb_path: string | null
          id: string
          max_error: number | null
          meta: Json | null
          piece_id: string
          preview_path: string | null
          provider: string | null
          render_paths: Json | null
          selected: boolean
          usdz_path: string | null
        }
        Insert: {
          attempt: number
          candidate?: number
          cost_usd?: number | null
          created_at?: string
          glb_path?: string | null
          id?: string
          max_error?: number | null
          meta?: Json | null
          piece_id: string
          preview_path?: string | null
          provider?: string | null
          render_paths?: Json | null
          selected?: boolean
          usdz_path?: string | null
        }
        Update: {
          attempt?: number
          candidate?: number
          cost_usd?: number | null
          created_at?: string
          glb_path?: string | null
          id?: string
          max_error?: number | null
          meta?: Json | null
          piece_id?: string
          preview_path?: string | null
          provider?: string | null
          render_paths?: Json | null
          selected?: boolean
          usdz_path?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "piece_models_piece_id_fkey"
            columns: ["piece_id"]
            isOneToOne: false
            referencedRelation: "admin_review_queue"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "piece_models_piece_id_fkey"
            columns: ["piece_id"]
            isOneToOne: false
            referencedRelation: "pieces"
            referencedColumns: ["id"]
          },
        ]
      }
      piece_photos: {
        Row: {
          created_at: string
          id: string
          piece_id: string
          position: number
          storage_path: string
        }
        Insert: {
          created_at?: string
          id?: string
          piece_id: string
          position?: number
          storage_path: string
        }
        Update: {
          created_at?: string
          id?: string
          piece_id?: string
          position?: number
          storage_path?: string
        }
        Relationships: [
          {
            foreignKeyName: "piece_photos_piece_id_fkey"
            columns: ["piece_id"]
            isOneToOne: false
            referencedRelation: "admin_review_queue"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "piece_photos_piece_id_fkey"
            columns: ["piece_id"]
            isOneToOne: false
            referencedRelation: "pieces"
            referencedColumns: ["id"]
          },
        ]
      }
      pieces: {
        Row: {
          attempt: number
          claimed_at: string | null
          created_at: string
          depth_cm: number
          error: string | null
          height_cm: number
          id: string
          kind: Database["public"]["Enums"]["piece_kind"]
          name: string
          notes: string | null
          rectilinear: boolean | null
          reject_reason: string | null
          review_note: string | null
          route: string | null
          status: Database["public"]["Enums"]["piece_status"]
          updated_at: string
          user_id: string
          width_cm: number
        }
        Insert: {
          attempt?: number
          claimed_at?: string | null
          created_at?: string
          depth_cm: number
          error?: string | null
          height_cm: number
          id?: string
          kind: Database["public"]["Enums"]["piece_kind"]
          name: string
          notes?: string | null
          rectilinear?: boolean | null
          reject_reason?: string | null
          review_note?: string | null
          route?: string | null
          status?: Database["public"]["Enums"]["piece_status"]
          updated_at?: string
          user_id?: string
          width_cm: number
        }
        Update: {
          attempt?: number
          claimed_at?: string | null
          created_at?: string
          depth_cm?: number
          error?: string | null
          height_cm?: number
          id?: string
          kind?: Database["public"]["Enums"]["piece_kind"]
          name?: string
          notes?: string | null
          rectilinear?: boolean | null
          reject_reason?: string | null
          review_note?: string | null
          route?: string | null
          status?: Database["public"]["Enums"]["piece_status"]
          updated_at?: string
          user_id?: string
          width_cm?: number
        }
        Relationships: [
          {
            foreignKeyName: "pieces_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          attribution: Json | null
          created_at: string
          email: string | null
          id: string
          is_admin: boolean
          plan: string | null
        }
        Insert: {
          attribution?: Json | null
          created_at?: string
          email?: string | null
          id: string
          is_admin?: boolean
          plan?: string | null
        }
        Update: {
          attribution?: Json | null
          created_at?: string
          email?: string | null
          id?: string
          is_admin?: boolean
          plan?: string | null
        }
        Relationships: []
      }
      purchases: {
        Row: {
          amount_cents: number
          created_at: string
          credits: number
          id: string
          pack: string
          status: string
          stripe_session_id: string
          user_id: string
        }
        Insert: {
          amount_cents: number
          created_at?: string
          credits: number
          id?: string
          pack: string
          status: string
          stripe_session_id: string
          user_id: string
        }
        Update: {
          amount_cents?: number
          created_at?: string
          credits?: number
          id?: string
          pack?: string
          status?: string
          stripe_session_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "purchases_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      admin_review_queue: {
        Row: {
          attempt: number | null
          candidate: number | null
          claimed_at: string | null
          cost_usd: number | null
          created_at: string | null
          depth_cm: number | null
          error: string | null
          glb_path: string | null
          height_cm: number | null
          id: string | null
          kind: Database["public"]["Enums"]["piece_kind"] | null
          max_error: number | null
          meta: Json | null
          model_attempt: number | null
          model_created_at: string | null
          model_id: string | null
          name: string | null
          notes: string | null
          preview_path: string | null
          provider: string | null
          rectilinear: boolean | null
          reject_reason: string | null
          render_paths: Json | null
          review_note: string | null
          route: string | null
          selected: boolean | null
          status: Database["public"]["Enums"]["piece_status"] | null
          updated_at: string | null
          usdz_path: string | null
          user_email: string | null
          user_id: string | null
          width_cm: number | null
        }
        Relationships: [
          {
            foreignKeyName: "pieces_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Functions: {
      approve_piece: { Args: { p_piece_id: string }; Returns: Json }
      claim_next_piece: {
        Args: never
        Returns: {
          attempt: number
          claimed_at: string | null
          created_at: string
          depth_cm: number
          error: string | null
          height_cm: number
          id: string
          kind: Database["public"]["Enums"]["piece_kind"]
          name: string
          notes: string | null
          rectilinear: boolean | null
          reject_reason: string | null
          review_note: string | null
          route: string | null
          status: Database["public"]["Enums"]["piece_status"]
          updated_at: string
          user_id: string
          width_cm: number
        }
        SetofOptions: {
          from: "*"
          to: "pieces"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      credit_balance: { Args: { p_user: string }; Returns: number }
      daily_piece_limit: { Args: never; Returns: number }
      grant_credits: {
        Args: {
          p_delta: number
          p_reason: Database["public"]["Enums"]["credit_reason"]
          p_session?: string
          p_user: string
        }
        Returns: number
      }
      pieces_created_today: { Args: { p_user: string }; Returns: number }
      reject_piece: {
        Args: { p_piece_id: string; p_reason: string }
        Returns: {
          attempt: number
          claimed_at: string | null
          created_at: string
          depth_cm: number
          error: string | null
          height_cm: number
          id: string
          kind: Database["public"]["Enums"]["piece_kind"]
          name: string
          notes: string | null
          rectilinear: boolean | null
          reject_reason: string | null
          review_note: string | null
          route: string | null
          status: Database["public"]["Enums"]["piece_status"]
          updated_at: string
          user_id: string
          width_cm: number
        }
        SetofOptions: {
          from: "*"
          to: "pieces"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      request_new_version: {
        Args: { p_piece_id: string }
        Returns: {
          attempt: number
          claimed_at: string | null
          created_at: string
          depth_cm: number
          error: string | null
          height_cm: number
          id: string
          kind: Database["public"]["Enums"]["piece_kind"]
          name: string
          notes: string | null
          rectilinear: boolean | null
          reject_reason: string | null
          review_note: string | null
          route: string | null
          status: Database["public"]["Enums"]["piece_status"]
          updated_at: string
          user_id: string
          width_cm: number
        }
        SetofOptions: {
          from: "*"
          to: "pieces"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      requeue_stale_pieces: { Args: { p_minutes?: number }; Returns: number }
    }
    Enums: {
      credit_reason: "purchase" | "consume" | "grant" | "refund" | "plan"
      piece_kind:
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
        | "otro"
      piece_status:
        | "queued"
        | "generating"
        | "review"
        | "ready"
        | "approved"
        | "needs_photos"
        | "rejected"
        | "failed"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {
      credit_reason: ["purchase", "consume", "grant", "refund", "plan"],
      piece_kind: [
        "mesa",
        "mesita",
        "aparador",
        "estanteria",
        "cabecero",
        "panel",
        "sofa",
        "sillon",
        "silla",
        "jarron",
        "lampara",
        "otro",
      ],
      piece_status: [
        "queued",
        "generating",
        "review",
        "ready",
        "approved",
        "needs_photos",
        "rejected",
        "failed",
      ],
    },
  },
} as const

// ---------------------------------------------------------------------------
// App aliases (not generated). Keep them when regenerating this file from
// `supabase/database.types.ts`.
export type Profile = Tables<"profiles">
export type Piece = Tables<"pieces">
export type PiecePhoto = Tables<"piece_photos">
export type PieceModel = Tables<"piece_models">
export type PieceStatus = Enums<"piece_status">
export type PieceKind = Enums<"piece_kind">
