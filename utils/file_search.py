"""Search file names through the Windows Search index."""

from __future__ import annotations


def search_indexed_files(query: str, limit: int = 100) -> list[str]:
    """Return indexed local file paths whose names contain the query."""
    normalized = query.strip()
    if not normalized:
        return []

    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    connection = None
    recordset = None
    try:
        connection = win32com.client.Dispatch("ADODB.Connection")
        connection.Open(
            "Provider=Search.CollatorDSO;Extended Properties='Application=Windows';"
        )
        escaped_query = normalized.replace("'", "''")
        escaped_query = escaped_query.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
        sql = (
            "SELECT TOP {limit} System.ItemPathDisplay "
            "FROM SystemIndex "
            "WHERE System.FileName LIKE '%{query}%' "
            "ORDER BY System.FileName"
        ).format(limit=max(1, min(limit, 500)), query=escaped_query)
        recordset, _ = connection.Execute(sql)
        paths: list[str] = []
        while not recordset.EOF:
            path = recordset.Fields.Item("System.ItemPathDisplay").Value
            if path:
                paths.append(str(path))
            recordset.MoveNext()
        return paths
    finally:
        if recordset is not None:
            recordset.Close()
        if connection is not None:
            connection.Close()
        pythoncom.CoUninitialize()
