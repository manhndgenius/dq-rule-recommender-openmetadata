export function renderSQLWithParams(sql, params) {
  if (!sql) return '';

  let result = sql;

  if (params && typeof params === 'object') {
    Object.entries(params).forEach(([key, value]) => {
      const placeholder = `:${key}`;
      if (!result.includes(placeholder)) return;

      let literal;
      if (value === null || value === undefined) {
        literal = 'NULL';
      } else if (typeof value === 'boolean') {
        literal = value ? 'TRUE' : 'FALSE';
      } else if (typeof value === 'number') {
        literal = String(value);
      } else if (Array.isArray(value)) {
        literal = `(${value.map((item) => (
          typeof item === 'string' ? `'${item.replace(/'/g, "''")}'` : item
        )).join(', ')})`;
      } else {
        literal = `'${String(value).replace(/'/g, "''")}'`;
      }

      result = result.replaceAll(placeholder, literal);
    });
  }

  return result;
}
