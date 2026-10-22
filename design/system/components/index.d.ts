import type * as React from 'react';

export type Family = 'care' | 'collaboration' | 'judgement' | 'curiosity' | 'risk';
/** 0 absent, 1 faint, 2 clear, 3 dominant; a two-judge median may be a half, such as 1.5. */
export type Intensity = number;
export type Trust = 'trusted' | 'provisional' | 'retired' | 'unrated';
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'stopped at budget';
export type Tone = 'neutral' | 'ok' | 'warn' | 'danger';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { variant?: 'primary' | 'secondary' }
export interface LinkButtonProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> { href?: string; onClick?: () => void; children?: React.ReactNode }
export interface FieldProps extends React.InputHTMLAttributes<HTMLInputElement> { label: string; hint?: string; error?: string; multiline?: boolean }
export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> { label: string; hint?: string; error?: string; options: Array<string | { value: string; label: string }> }
export interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> { label: string; hint?: string }
export interface RadioProps extends React.InputHTMLAttributes<HTMLInputElement> { label: string; hint?: string; name: string }
export interface TabsProps { tabs: Array<{ id: string; label: string; count?: number }>; label: string; value?: string; onChange?: (id: string) => void; panels?: Record<string, React.ReactNode> }
export interface DialogProps { title: string; children?: React.ReactNode; actions?: React.ReactNode; open?: boolean; onClose?: () => void; inline?: boolean }
export interface ToastProps { children: React.ReactNode; tone?: 'ok' | 'warn' | 'danger' | 'info'; action?: React.ReactNode }
export interface NoticeProps { children: React.ReactNode; title?: string; tone?: 'info' | 'danger' }
export interface CardProps { title?: string; actions?: React.ReactNode; children?: React.ReactNode; label?: string; className?: string }
export interface PageHeaderProps { title: string; intro?: string; note?: string; area?: 'home' | 'agents' | 'inquiry' | 'tally' | 'ethos' | 'review' | 'reports' | 'settings'; actions?: React.ReactNode }
export interface BadgeProps { tone?: Tone; icon?: React.ReactNode; children: React.ReactNode }
export interface MonoProps { children: React.ReactNode; truncate?: number; plain?: boolean; title?: string }
export interface NavItem { label: string; href: string }
export interface NavProps { current?: string; items?: NavItem[]; onNavigate?: (item: NavItem) => void }
export interface AppShellProps extends NavProps { user?: { name: string; role?: string }; children?: React.ReactNode }

export interface Column<Row> { key: string; label: string; align?: 'left' | 'right'; render?: (row: Row) => React.ReactNode; sortValue?: (row: Row) => number | string; sortable?: boolean; cellStyle?: (row: Row) => React.CSSProperties }
export interface DataTableProps<Row = Record<string, unknown>> { columns: Column<Row>[]; rows: Row[]; density?: 'comfortable' | 'dense'; caption?: string; initialSort?: { key: string; dir: 'asc' | 'desc' }; sortable?: boolean; rowHeaders?: boolean; maxHeight?: number | string }
export interface ScoreCellProps { value: number; max?: number; samples?: number[]; href?: string; label?: string; threshold?: number; concern?: boolean }
export interface HeatmapProps { dimensions: Array<{ key: string; label: string }>; builtIn?: Array<{ key: string; label: string }>; transcripts: Array<{ id: string; label: string; seed?: string; href?: string; scores: Record<string, { value: number; samples?: number[]; href?: string }> }>; caption?: string }
export interface Rate { version: string; rate: number; low: number; high: number; reps?: number[]; worse?: boolean }
export interface RateChartProps { data: Rate[]; title?: string; max?: number }
export interface RateTableProps { data: Rate[]; caption?: string }
export interface IntervalBarProps { value: number; low: number; high: number; label?: string; family?: Family; max?: number }

export interface StatusBadgeProps { status: RunStatus }
export interface RunProgressProps { counts: Partial<Record<RunStatus, number>>; total?: number; unit?: string }
export interface ProvenanceProps { run: { status?: RunStatus; prompt?: { agent: string; version: string; href?: string }; models?: Record<string, string>; mode?: string; route?: string; configHash?: string; promptSha?: string; seedHash?: string; taxonomyVersion?: string; engines?: string[]; commit?: string; tokens?: { used: number; budget: number }; cost?: string; started?: string; finished?: string; logHref?: string } }

export interface MessageViewProps { role: 'system' | 'member' | 'agent' | 'tool'; children: React.ReactNode; author?: string; index?: number; toolCalls?: Array<{ name: string; args: string }>; thinking?: 'summary' | 'full' }
export interface CitedProps { text: string; hrefFor?: (n: string) => string }
export interface ContentNoteProps { topic: string; href?: string; linkText?: string }
export interface FullThinkingProps { children?: React.ReactNode; canRead?: boolean; onOpen?: () => void }

export interface LabelChipProps { family: Family; label: string; trust?: Trust; agreement?: number }
export interface TrustBadgeProps { trust: Trust; agreement?: number }
export interface HighlightedProps { family: Family; label: string; median: Intensity; children: React.ReactNode; judges?: number; selected?: boolean; onSelect?: () => void }
export interface ProfileCell { label: string; family: Family; observed: Intensity; expected: { kind: 'present' | 'absent' | 'either'; min?: number; max?: number }; disputed?: boolean }
export interface ProfileStripProps { cells: ProfileCell[]; label?: string }
export interface FindingPaneProps { label: string; family: Family; median: Intensity; judges: Array<{ model: string; intensity: Intensity; quotes?: string[]; dropped?: string[]; rationale?: string }>; definition?: string; trust?: Trust; agreement?: number; onClose?: () => void }
export interface TurnTimelineProps { rows: Array<{ label: string; family: Family; values: Intensity[] }>; replies?: number; label?: string }
export interface CompareViewProps { a: { name: string }; b: { name: string }; rows: Array<{ label: string; family: Family; a: number; b: number; diff: number; low: number; high: number }>; span?: number }
export interface WitnessPaneProps { text: string; signals: Array<{ id: string; name: string; kind: 'probe' | 'persona' | 'autoencoder'; spans: Array<{ start: number; end: number; value: number }> }>; model?: string; active?: string; explanations?: Array<{ quote: string; text: string }> }

export interface DiffLine { n: number; text: string; change?: 'added' | 'removed' }
export interface DiffViewProps { left: { title: string; lines: DiffLine[] }; right: { title: string; lines: DiffLine[] } }
export interface EmptyStateProps { children: React.ReactNode; title?: string; action?: React.ReactNode }
export interface LoadingStateProps { label?: string }
export interface ReliefProps { variant?: 'route' | 'hairpin'; width?: number | string; height?: number | string; preserve?: string; className?: string; style?: React.CSSProperties; fade?: boolean }

export declare function Button(props: ButtonProps): React.ReactElement;
export declare function LinkButton(props: LinkButtonProps): React.ReactElement;
export declare function Field(props: FieldProps): React.ReactElement;
export declare function Select(props: SelectProps): React.ReactElement;
export declare function Checkbox(props: CheckboxProps): React.ReactElement;
export declare function Radio(props: RadioProps): React.ReactElement;
export declare function Tabs(props: TabsProps): React.ReactElement;
export declare function Dialog(props: DialogProps): React.ReactElement | null;
export declare function Toast(props: ToastProps): React.ReactElement;
export declare function Notice(props: NoticeProps): React.ReactElement;
export declare function Card(props: CardProps): React.ReactElement;
export declare function PageHeader(props: PageHeaderProps): React.ReactElement;
export declare function Badge(props: BadgeProps): React.ReactElement;
export declare function Mono(props: MonoProps): React.ReactElement;
export declare function AppShell(props: AppShellProps): React.ReactElement;
export declare function Nav(props: NavProps): React.ReactElement;
export declare function DataTable<Row>(props: DataTableProps<Row>): React.ReactElement;
export declare function ScoreCell(props: ScoreCellProps): React.ReactElement;
export declare function Heatmap(props: HeatmapProps): React.ReactElement;
export declare function RateChart(props: RateChartProps): React.ReactElement;
export declare function RateTable(props: RateTableProps): React.ReactElement;
export declare function IntervalBar(props: IntervalBarProps): React.ReactElement;
export declare function StatusBadge(props: StatusBadgeProps): React.ReactElement;
export declare function RunProgress(props: RunProgressProps): React.ReactElement;
export declare function Provenance(props: ProvenanceProps): React.ReactElement;
export declare function MessageView(props: MessageViewProps): React.ReactElement;
export declare function Cited(props: CitedProps): React.ReactElement;
export declare function ContentNote(props: ContentNoteProps): React.ReactElement;
export declare function FullThinking(props: FullThinkingProps): React.ReactElement;
export declare function LabelChip(props: LabelChipProps): React.ReactElement;
export declare function TrustBadge(props: TrustBadgeProps): React.ReactElement;
export declare function Highlighted(props: HighlightedProps): React.ReactElement;
export declare function ProfileStrip(props: ProfileStripProps): React.ReactElement;
export declare function FindingPane(props: FindingPaneProps): React.ReactElement;
export declare function TurnTimeline(props: TurnTimelineProps): React.ReactElement;
export declare function CompareView(props: CompareViewProps): React.ReactElement;
export declare function WitnessPane(props: WitnessPaneProps): React.ReactElement;
export declare function DiffView(props: DiffViewProps): React.ReactElement;
export declare function EmptyState(props: EmptyStateProps): React.ReactElement;
export declare function LoadingState(props: LoadingStateProps): React.ReactElement;
export declare function Relief(props: ReliefProps): React.ReactElement;
