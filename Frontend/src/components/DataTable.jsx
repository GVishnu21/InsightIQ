// Cells can hold lists (a column's example values) or nothing at all (a missing value).
function show(value) {
  if (value === null || value === undefined) return "";
  return Array.isArray(value) ? value.join(", ") : String(value);
}

// A generic table: the headers come from the keys of the first row, so one
// component displays previews, statistics and query results alike.
function DataTable({ rows }) {
  if (!rows?.length) {
    return <p className="empty">Nothing to show.</p>;
  }

  const headers = Object.keys(rows[0]);

  return (
    <div className="table-scroll">
      <table className="data">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header} scope="col">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {headers.map((header) => (
                <td key={header}>{show(row[header])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;
