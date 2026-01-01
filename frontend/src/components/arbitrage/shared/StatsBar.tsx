interface StatItem {
  value: number | string;
  label: string;
  color: string;
}

interface StatsBarProps {
  stats: StatItem[];
}

export function StatsBar({ stats }: StatsBarProps) {
  return (
    <div className={`grid gap-2 bg-slate-800 rounded-lg p-3 text-center`} style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}>
      {stats.map((stat, idx) => (
        <div key={idx}>
          <div className={`text-lg font-bold ${stat.color}`}>{stat.value}</div>
          <div className="text-xs text-gray-500">{stat.label}</div>
        </div>
      ))}
    </div>
  );
}
