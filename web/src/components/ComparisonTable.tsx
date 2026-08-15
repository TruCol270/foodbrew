import type { Comparison } from '../api/types'

const SECTIONS = ['Verdict', 'Setup', 'Rules', 'Dose per serving', 'Occasion envelope']

export function ComparisonTable({ comparison, changedOnly }: {
  comparison: Comparison
  changedOnly: boolean
}) {
  const rows = changedOnly ? comparison.rows.filter((r) => r.changed) : comparison.rows

  return (
    <table data-testid="comparison">
      <thead>
        <tr>
          <th />
          {comparison.columns.map((column) => (
            <th key={column.evaluation_id} className={`headline--${column.headline.toLowerCase()}`}>
              {column.label}
            </th>
          ))}
        </tr>
      </thead>
      {SECTIONS.map((section) => {
        const sectionRows = rows.filter((r) => r.section === section)
        if (sectionRows.length === 0) return null
        return (
          <tbody key={section}>
            <tr><th colSpan={comparison.columns.length + 1}>{section}</th></tr>
            {sectionRows.map((row) => (
              <tr key={row.key} data-testid={`row-${row.key}`}
                  className={row.changed ? 'row--changed' : undefined}>
                <th scope="row">{row.label}</th>
                {row.cells.map((cell, index) => (
                  <td key={index}
                      className={[
                        row.changed ? 'cell--changed' : '',
                        cell.present ? '' : 'cell--absent',
                      ].join(' ')}>
                    {cell.text}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        )
      })}
    </table>
  )
}
