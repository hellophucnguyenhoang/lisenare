import pandas as pd

from app.schemas.brick import (
    GrammarPoint,
    SentenceFunction,
    SentenceStructure,
    UnitType,
)

# Lấy danh sách các giá trị hợp lệ từ Enum
VALID_UNITS = [e.value for e in UnitType]
VALID_STRUCTURES = [e.value for e in SentenceStructure]
VALID_FUNCTIONS = [e.value for e in SentenceFunction]
VALID_GRAMMARS = [e.value for e in GrammarPoint]


def check_metadata(file_path="metadata.csv"):
    try:
        df = pd.read_csv(file_path)

        # Hàm kiểm tra từng dòng
        def validate_row(row):
            errors = []

            u_type = str(row["unit_type"]).strip()
            struct = (
                str(row["structure"]).strip()
                if pd.notna(row["structure"])
                else ""
            )
            func = (
                str(row["function"]).strip()
                if pd.notna(row["function"])
                else ""
            )
            grammars = (
                str(row["grammar_points"]).strip()
                if pd.notna(row["grammar_points"])
                else ""
            )

            # 1. Kiểm tra unit_type
            if u_type not in VALID_UNITS:
                errors.append(f"Invalid unit_type: {u_type}")

            # 2. Kiểm tra ràng buộc structure và function
            if u_type == "sentence":
                if not struct or struct not in VALID_STRUCTURES:
                    errors.append(
                        f"Sentence must have valid structure (got: '{struct}')"
                    )
                if not func or func not in VALID_FUNCTIONS:
                    errors.append(
                        f"Sentence must have valid function (got: '{func}')"
                    )
            else:
                # Nếu không phải sentence thì structure và function phải null/rỗng
                if struct != "":
                    errors.append(f"Structure must be null for {u_type}")
                if func != "":
                    errors.append(f"Function must be null for {u_type}")

            # 3. Kiểm tra grammar_points (giả sử phân cách bằng dấu phẩy)
            if grammars:
                gp_list = [g.strip() for g in grammars.split("|") if g.strip()]
                for gp in gp_list:
                    if gp not in VALID_GRAMMARS:
                        errors.append(f"Invalid grammar_point: {gp}")

            return "; ".join(errors) if errors else None

        # Áp dụng kiểm tra
        df["error_details"] = df.apply(validate_row, axis=1)

        # Lọc ra các dòng có lỗi
        errors_df = df[df["error_details"].notna()]

        if not errors_df.empty:
            errors_df.to_csv("errors_report.csv", index=False)
            print(
                f"❌ Tìm thấy {len(errors_df)} dòng lỗi. Chi tiết tại 'errors_report.csv'."
            )
        else:
            print("✅ File hợp lệ! Không có lỗi ràng buộc nào.")

    except FileNotFoundError:
        print("Không tìm thấy file metadata.csv")
    except Exception as e:
        print(f"Lỗi khi xử lý: {e}")


if __name__ == "__main__":
    check_metadata()
