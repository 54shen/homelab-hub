# ============================================================
# Shared Center — 字段映射 API（英文 key → 中文显示名）
# ============================================================
import csv
import io
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
from models import FieldMapping, KvEntry
from schemas import FieldMappingCreate, FieldMappingUpdate, FieldMappingOut, ApiResponse
from auth import auth_write

router = APIRouter(prefix="/api", tags=["字段映射"])


# ---- 列表 ----
@router.get("/field-mappings", response_model=list[FieldMappingOut])
def list_mappings(db: Session = Depends(get_db)):
    return db.query(FieldMapping).order_by(FieldMapping.id).all()


# ---- 扫描 KV 表中未映射的 field key（必须在 /{id} 之前注册） ----
@router.get("/field-mappings/unmapped")
def list_unmapped(db: Session = Depends(get_db)):
    """扫描所有 KV key 的后缀，返回还没有映射的 field key 列表"""
    mapped = {m.field_key for m in db.query(FieldMapping).all()}
    all_keys = db.query(KvEntry.key).all()
    seen = set()
    unmapped = []
    for (k,) in all_keys:
        suffix = k.rsplit(".", 1)[-1] if "." in k else k
        if suffix not in mapped and suffix not in seen:
            seen.add(suffix)
            unmapped.append(suffix)
    unmapped.sort()
    return unmapped


# ---- 导出空白模板 CSV（必须在 /{id} 之前注册） ----
@router.get("/field-mappings/export/template")
def export_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["field_key", "display_name"])
    writer.writerow(["", "（在此填写英文key）", "（在此填写中文名）"])
    content = output.getvalue()
    output.close()

    from fastapi.responses import Response
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=field_mappings_template.csv"}
    )


# ---- 新增 ----
@router.post("/field-mappings", response_model=FieldMappingOut)
def create_mapping(req: FieldMappingCreate, db: Session = Depends(get_db), token=Depends(auth_write)):
    key = req.field_key.strip()
    existing = db.query(FieldMapping).filter(FieldMapping.field_key == key).first()
    if existing:
        existing.display_name = req.display_name.strip()
        db.commit()
        db.refresh(existing)
        return existing
    m = FieldMapping(field_key=key, display_name=req.display_name.strip())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ---- 导入 CSV ----
@router.post("/field-mappings/import", response_model=ApiResponse)
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db), token=Depends(auth_write)):
    content = await file.read()
    for enc in ["utf-8-sig", "utf-8", "gbk"]:
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return ApiResponse(success=False, message="无法解析文件编码，请使用 UTF-8 或 GBK")

    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or "field_key" not in header or "display_name" not in header:
        return ApiResponse(success=False, message="CSV 格式错误：需要 field_key 和 display_name 两列")

    inserted = 0
    updated = 0
    for row in reader:
        if not row or len(row) < 2:
            continue
        key = row[0].strip()
        name = row[1].strip()
        if not key or not name:
            continue
        existing = db.query(FieldMapping).filter(FieldMapping.field_key == key).first()
        if existing:
            existing.display_name = name
            updated += 1
        else:
            db.add(FieldMapping(field_key=key, display_name=name))
            inserted += 1

    db.commit()
    return ApiResponse(success=True, message=f"导入完成：新增 {inserted} 条，更新 {updated} 条")


# ---- 修改 ----
@router.put("/field-mappings/{mapping_id}", response_model=FieldMappingOut)
def update_mapping(mapping_id: int, req: FieldMappingUpdate, db: Session = Depends(get_db), token=Depends(auth_write)):
    m = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if not m:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "映射不存在"})
    if req.field_key is not None:
        m.field_key = req.field_key.strip()
    if req.display_name is not None:
        m.display_name = req.display_name.strip()
    db.commit()
    db.refresh(m)
    return m


# ---- 删除 ----
@router.delete("/field-mappings/{mapping_id}", response_model=ApiResponse)
def delete_mapping(mapping_id: int, db: Session = Depends(get_db), token=Depends(auth_write)):
    m = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if m:
        db.delete(m)
        db.commit()
    return ApiResponse(success=True, message="已删除")
