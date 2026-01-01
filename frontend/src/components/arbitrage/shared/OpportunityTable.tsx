interface TableColumn {
  key: string;
  label: string;
  align?: 'left' | 'right' | 'center';
  bold?: boolean;
}

interface OpportunityTableProps {
  columns: TableColumn[];
  data: any[];
  onRowClick?: (row: any, idx: number) => void;
  getRowClassName?: (row: any, idx: number) => string;
  renderCell: (row: any, column: TableColumn, idx: number) => React.ReactNode;
  emptyMessage?: React.ReactNode;
  footerMessage?: string;
}

export function OpportunityTable({
  columns,
  data,
  onRowClick,
  getRowClassName,
  renderCell,
  emptyMessage = 'No data available',
  footerMessage
}: OpportunityTableProps) {
  if (data.length === 0) {
    return (
      <div className="text-gray-500 text-center py-4">
        {emptyMessage}
      </div>
    );
  }

  return (
    <>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-400 border-b border-slate-600">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`pb-2 px-1 ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : ''} ${col.bold ? 'font-bold' : ''}`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr
              key={idx}
              onClick={() => onRowClick?.(row, idx)}
              className={`border-b border-slate-700/50 ${onRowClick ? 'cursor-pointer hover:bg-slate-700/50 transition-colors' : ''} ${getRowClassName?.(row, idx) || ''}`}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`py-2 px-1 ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : ''}`}
                >
                  {renderCell(row, col, idx)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {footerMessage && (
        <div className="text-xs text-gray-500 mt-3 text-center">
          {footerMessage}
        </div>
      )}
    </>
  );
}
