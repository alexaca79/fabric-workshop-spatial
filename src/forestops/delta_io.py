"""Delta reads and writes, including the geometry round trip.

Spark has no geometry type, so geometry travels as well-known binary with the
spatial reference identifier in its own column. Every function here enforces
that pairing, because a WKB blob with no declared CRS is a future incident.
"""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import pandas as pd


def geodataframe_to_spark(gdf: gpd.GeoDataFrame, spark, geometry_col: str = "geometry"):
    """Convert a GeoDataFrame to a Spark DataFrame with WKB geometry."""
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS; declare it before writing to Delta")

    frame = gdf.copy()
    frame["geometry_wkb"] = frame[geometry_col].apply(lambda geom: geom.wkb if geom is not None else None)
    frame["srid"] = gdf.crs.to_epsg()
    frame = pd.DataFrame(frame.drop(columns=[geometry_col]))

    # Pandas nullable integer types do not survive the Arrow conversion cleanly.
    for column in frame.columns:
        if str(frame[column].dtype) == "Int64":
            frame[column] = frame[column].astype("object").where(frame[column].notna(), None)

    return spark.createDataFrame(frame)


def spark_to_geodataframe(sdf, wkb_col: str = "geometry_wkb", srid_col: str = "srid") -> gpd.GeoDataFrame:
    """Rebuild a GeoDataFrame from a Delta table, restoring the CRS."""
    from shapely import wkb

    pdf = sdf.toPandas()
    if pdf.empty:
        return gpd.GeoDataFrame(pdf, geometry=[], crs=None)

    srids = pdf[srid_col].dropna().unique()
    if len(srids) > 1:
        raise ValueError(
            f"table mixes spatial reference systems {sorted(srids)}. Reproject to one CRS before reading; "
            "a mixed-CRS frame produces geometry in two different places with no error."
        )

    geometry = [wkb.loads(bytes(value)) if value is not None else None for value in pdf[wkb_col]]
    return gpd.GeoDataFrame(
        pdf.drop(columns=[wkb_col]),
        geometry=geometry,
        crs=int(srids[0]) if len(srids) else None,
    )


def write_delta(
    sdf,
    table: str,
    mode: str = "overwrite",
    merge_schema: bool = False,
    partition_by: list[str] | None = None,
) -> None:
    """Write a Spark DataFrame to a managed Delta table."""
    writer = sdf.write.format("delta").mode(mode)
    if merge_schema:
        writer = writer.option("mergeSchema", "true")
    if mode == "overwrite":
        writer = writer.option("overwriteSchema", "true")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.saveAsTable(table)


def append_bronze(sdf, table: str, partition_by: list[str] | None = None) -> None:
    """Append to a bronze table.

    Bronze is append-only by contract. Overwriting it destroys the ability to
    explain a number that was published last month, which is the entire reason
    the layer exists.
    """
    write_delta(sdf, table, mode="append", merge_schema=True, partition_by=partition_by)


def upsert_by_key(spark, sdf, table: str, keys: list[str]) -> None:
    """Merge rows into a table on the supplied business key.

    Used for silver and gold, where re-running a period must replace that
    period rather than duplicating it.
    """
    if not spark.catalog.tableExists(table):
        write_delta(sdf, table, mode="overwrite")
        return

    staging = f"_staging_{table}"
    sdf.createOrReplaceTempView(staging)
    condition = " AND ".join(f"target.{k} = source.{k}" for k in keys)
    spark.sql(
        f"""
        MERGE INTO {table} AS target
        USING {staging} AS source
        ON {condition}
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )


def read_table(spark, table: str) -> pd.DataFrame:
    """Read a Delta table into pandas, raising a useful message when absent."""
    if not spark.catalog.tableExists(table):
        raise FileNotFoundError(
            f"table '{table}' does not exist. Run the notebook that produces it before this one; "
            "the notebooks are ordered for a reason."
        )
    return spark.table(table).toPandas()


def table_summary(spark, tables: dict[str, str]) -> pd.DataFrame:
    """Row counts for every pipeline table, for the end-of-notebook check."""
    records: list[dict[str, Any]] = []
    for key, name in tables.items():
        if spark.catalog.tableExists(name):
            records.append({"role": key, "table": name, "rows": spark.table(name).count(), "exists": True})
        else:
            records.append({"role": key, "table": name, "rows": 0, "exists": False})
    return pd.DataFrame(records)
