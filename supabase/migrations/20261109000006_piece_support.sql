-- «¿Cómo se apoya la pieza?» (form question for rectilinear pieces). The worker maps it to
-- the parametric layout of route E: patas → table, paneles → panel_table (sides),
-- caja → box (box_legs when the notes mention «patas»/«zócalo»), no_se/null → heuristic.

alter table public.pieces
  add column support text
  check (support in ('patas', 'paneles', 'caja', 'no_se'));

-- Clients may set it on insert, like the other form fields.
grant insert (support) on public.pieces to authenticated;
