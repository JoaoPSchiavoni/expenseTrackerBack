"""Generate a polished, portable monthly financial report."""

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _money(value: Decimal, currency: str) -> str:
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{currency} {text}"


def build_monthly_report_pdf(
    *,
    month: str,
    user_name: str,
    currency: str,
    income: Decimal,
    expense: Decimal,
    categories: list[tuple[int | None, str, Decimal]],
) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Relatório financeiro {month}",
        author="Spendly",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Spendly", styles["Title"]),
        Paragraph(f"Relatório financeiro mensal · {month}", styles["Heading2"]),
        Paragraph(f"Gerado para {user_name}", styles["BodyText"]),
        Spacer(1, 10 * mm),
    ]
    net = income - expense
    summary = Table(
        [
            ["Receitas", "Despesas", "Saldo do mês"],
            [_money(income, currency), _money(expense, currency), _money(net, currency)],
        ],
        colWidths=[55 * mm, 55 * mm, 55 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3B82F6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EFF6FF")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend([summary, Spacer(1, 10 * mm), Paragraph("Gastos por categoria", styles["Heading2"])])
    category_rows: list[list[str]] = [["Categoria", "Total", "% das despesas"]]
    for _, name, total in categories:
        percentage = Decimal("0") if expense == 0 else total / expense * Decimal("100")
        category_rows.append([name, _money(total, currency), f"{percentage:.1f}%"])
    if len(category_rows) == 1:
        category_rows.append(["Nenhum gasto no período", "—", "—"])
    table = Table(category_rows, colWidths=[75 * mm, 55 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 12 * mm),
            Paragraph(
                "Este relatório foi criado automaticamente a partir dos lançamentos registrados no Spendly.",
                styles["BodyText"],
            ),
        ]
    )
    document.build(story)
    return output.getvalue()
