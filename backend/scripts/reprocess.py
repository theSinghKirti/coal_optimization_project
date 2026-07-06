import sys
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.modules.documents import repository as doc_repo
from app.modules.documents.models import Document, VariableCost
from app.modules.documents.service import _build_known_plant_tokens, _resolve_plant_id_for_token
from app.modules.documents.variable_cost_parser import parse_variable_cost_pdf

# Import other models to ensure configure_mappers works


def reprocess_document(doc_id_str: str):
    db = SessionLocal()
    try:
        # 1. Fetch the document
        doc = db.get(Document, doc_id_str)
        if not doc:
            print(f"Document with ID {doc_id_str} not found in database.")
            return
        
        print(f"Found document: {doc.original_filename}")
        print(f"Storage path: {doc.storage_path}")
        
        # Read the file
        file_path = Path(doc.storage_path)
        if not file_path.exists():
            print(f"File not found on disk at {file_path}")
            return
            
        with open(file_path, "rb") as f:
            content = f.read()
            
        # 2. Build plant tokens
        known_tokens = _build_known_plant_tokens(db)
        
        # 3. Parse the PDF
        parse_result = parse_variable_cost_pdf(content, known_tokens)
        
        if not parse_result.text_extracted:
            print("Failed to extract text from PDF:")
            print("\n".join(parse_result.notes))
            return
            
        print(f"Parsed {len(parse_result.rows)} rows successfully.")
        
        # 4. Clear existing variable costs associated with this document
        deleted = db.query(VariableCost).filter(VariableCost.document_id == doc.id).delete()
        print(f"Cleared {deleted} existing VariableCost records.")
        
        # 5. Insert new variable cost records
        created_count = 0
        for row in parse_result.rows:
            plant_id = _resolve_plant_id_for_token(db, row.matched_plant_token) if row.confident else None
            needs_review = not row.confident or plant_id is None
            
            doc_repo.create_variable_cost(
                db,
                plant_id=plant_id,
                document_id=doc.id,
                source_plant_name=row.source_plant_name,
                effective_date=row.effective_date,
                variable_cost_per_unit=row.variable_cost_per_unit or 0,
                unit="Rs/kWh",
                needs_review=needs_review,
            )
            created_count += 1
            print(
                f"  [created] {row.source_plant_name}: "
                f"{row.variable_cost_per_unit} (needs_review={needs_review})"
            )
            
        # Update document state if needed
        if any(not r.confident for r in parse_result.rows) or not parse_result.rows:
            doc.needs_review = True
            doc.review_status = "needs_review"
        else:
            doc.needs_review = False
            doc.review_status = "approved"
            
        db.commit()
        print(f"Successfully reprocessed document. Created {created_count} variable cost records.")
        
    except Exception as e:
        db.rollback()
        print(f"Error during reprocessing: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    doc_id = "cb4f1555-457f-44f7-823b-11f36c83acc1"
    reprocess_document(doc_id)
