"""Terminal and HTML report generation for sca-triage results.

Provides rich-based terminal output and standalone HTML reports suitable
for attaching to compliance documentation.
"""

from __future__ import annotations

import base64
import pathlib
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .tvla import TVLAResult
from .pairwise import PairwiseResult
from .permutation_mi import MIResult


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

def _verdict(
    tvla_result: TVLAResult,
    pairwise_results: List[PairwiseResult],
    mi_results: List[MIResult],
) -> Tuple[str, str, str]:
    """Determine the final triage verdict.

    Parameters
    ----------
    tvla_result : TVLAResult
        Stage 1 result.
    pairwise_results : list[PairwiseResult]
        Stage 2 results (one per target).
    mi_results : list[MIResult]
        Stage 3 results (one per target).

    Returns
    -------
    tuple[str, str, str]
        ``(verdict_label, verdict_detail, color)`` where *color* is a
        rich/CSS colour name.
    """
    tvla_failed = not tvla_result.passed

    any_pairwise_significant = any(pr.any_significant for pr in pairwise_results)
    any_mi_significant = any(mi.significant for mi in mi_results)
    has_stage2 = len(pairwise_results) > 0

    if tvla_failed and has_stage2 and not any_pairwise_significant and not any_mi_significant:
        return (
            "FALSE POSITIVE (Temporal Drift Confound)",
            "TVLA fails but no secret-dependent leakage detected by "
            "pairwise or MI tests. The timing difference is attributable "
            "to temporal drift in sequential data collection, not to "
            "key-dependent behaviour.",
            "green",
        )
    elif tvla_failed and not has_stage2:
        return (
            "TVLA FAIL — Stage 2 required for triage",
            "TVLA reports leakage but Stage 2 (pairwise secret-group "
            "decomposition) was not run. Re-run with --secret-labels "
            "to determine whether this is a false positive or real leakage.",
            "yellow",
        )
    elif any_pairwise_significant or any_mi_significant:
        return (
            "POTENTIAL REAL LEAKAGE \u2014 INVESTIGATE",
            "One or more secret-dependent statistical tests reached "
            "significance. Further investigation is required to determine "
            "whether the leakage is exploitable.",
            "red",
        )
    else:
        return (
            "NO LEAKAGE DETECTED",
            "TVLA passed and no secret-dependent differences found.",
            "green",
        )


# ---------------------------------------------------------------------------
# Terminal report
# ---------------------------------------------------------------------------

def print_terminal_report(
    tvla_result: TVLAResult,
    pairwise_results: List[PairwiseResult],
    mi_results: List[MIResult],
    quick: bool = False,
) -> None:
    """Print a rich-formatted triage report to the terminal.

    Parameters
    ----------
    tvla_result : TVLAResult
        Stage 1 result.
    pairwise_results : list[PairwiseResult]
        Stage 2 results.
    mi_results : list[MIResult]
        Stage 3 results (empty when ``quick=True``).
    quick : bool
        If ``True``, Stage 3 was skipped.
    """
    console = Console()

    # ---- Stage 1 Panel ----------------------------------------------------
    tvla_color = "red" if not tvla_result.passed else "green"
    tvla_status = "FAIL" if not tvla_result.passed else "PASS"

    stage1_text = Text()
    stage1_text.append(f"  Welch's t-statistic : {tvla_result.t_statistic:+.4f}\n")
    stage1_text.append(f"  |t|                 : {abs(tvla_result.t_statistic):.4f}\n")
    stage1_text.append(f"  Threshold           : {tvla_result.threshold}\n")
    stage1_text.append(f"  p-value             : {tvla_result.p_value:.2e}\n")
    stage1_text.append(f"  Variance ratio      : {tvla_result.variance_ratio:.4f}\n")
    stage1_text.append(f"  n(fixed)            : {tvla_result.n_fixed:,}\n")
    stage1_text.append(f"  n(random)           : {tvla_result.n_random:,}\n")
    stage1_text.append(f"  Result              : ", style="bold")
    stage1_text.append(tvla_status, style=f"bold {tvla_color}")

    console.print(Panel(
        stage1_text,
        title="[bold]Stage 1: TVLA (Fixed-vs-Random)[/bold]",
        border_style=tvla_color,
    ))

    # ---- Stage 2 Panel ----------------------------------------------------
    if pairwise_results:
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Target")
        table.add_column("n(g0)")
        table.add_column("n(g1)")
        table.add_column("Welch t")
        table.add_column("Welch p")
        table.add_column("Cohen's d")
        table.add_column("KS p")
        table.add_column("Significant?")

        for pr in pairwise_results:
            sig_style = "bold red" if pr.any_significant else "bold green"
            sig_label = "YES" if pr.any_significant else "NO"
            table.add_row(
                pr.target_name,
                str(pr.n_group0),
                str(pr.n_group1),
                f"{pr.welch_t:+.4f}",
                f"{pr.welch_p:.2e}",
                f"{pr.cohens_d:.4f}",
                f"{pr.ks_p:.2e}",
                Text(sig_label, style=sig_style),
            )

        any_sig = any(pr.any_significant for pr in pairwise_results)
        pw_color = "red" if any_sig else "green"
        console.print(Panel(
            table,
            title="[bold]Stage 2: Pairwise Secret-Group Decomposition[/bold]",
            border_style=pw_color,
        ))
    else:
        console.print(Panel(
            "[dim]No secret labels available -- stage skipped.[/dim]",
            title="[bold]Stage 2: Pairwise Secret-Group Decomposition[/bold]",
            border_style="yellow",
        ))

    # ---- Stage 3 Panel ----------------------------------------------------
    if quick:
        console.print(Panel(
            "[dim]Skipped (--quick flag).[/dim]",
            title="[bold]Stage 3: Permutation MI Test[/bold]",
            border_style="yellow",
        ))
    elif mi_results:
        mi_table = Table(show_header=True, header_style="bold cyan", expand=True)
        mi_table.add_column("Target")
        mi_table.add_column("Observed MI")
        mi_table.add_column("Null Mean")
        mi_table.add_column("Null Std")
        mi_table.add_column("p-value")
        mi_table.add_column("Shuffles")
        mi_table.add_column("Significant?")

        for mi in mi_results:
            sig_style = "bold red" if mi.significant else "bold green"
            sig_label = "YES" if mi.significant else "NO"
            mi_table.add_row(
                mi.target_name,
                f"{mi.observed_mi:.6f}",
                f"{mi.null_mean:.6f}",
                f"{mi.null_std:.6f}",
                f"{mi.p_value:.4f}",
                str(mi.n_shuffles),
                Text(sig_label, style=sig_style),
            )

        any_mi_sig = any(mi.significant for mi in mi_results)
        mi_color = "red" if any_mi_sig else "green"
        console.print(Panel(
            mi_table,
            title="[bold]Stage 3: Permutation MI Test[/bold]",
            border_style=mi_color,
        ))
    else:
        console.print(Panel(
            "[dim]No secret labels available -- stage skipped.[/dim]",
            title="[bold]Stage 3: Permutation MI Test[/bold]",
            border_style="yellow",
        ))

    # ---- Final Verdict Panel ----------------------------------------------
    label, detail, color = _verdict(tvla_result, pairwise_results, mi_results)

    verdict_text = Text()
    verdict_text.append(f"\n  {label}\n\n", style=f"bold {color}")
    verdict_text.append(f"  {detail}\n", style="dim")

    console.print(Panel(
        verdict_text,
        title="[bold]Final Verdict[/bold]",
        border_style=color,
        padding=(1, 2),
    ))


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(
    tvla_result: TVLAResult,
    pairwise_results: List[PairwiseResult],
    mi_results: List[MIResult],
    plot_paths: Optional[Dict[str, str]] = None,
    quick: bool = False,
) -> str:
    """Generate a complete standalone HTML report.

    Parameters
    ----------
    tvla_result : TVLAResult
        Stage 1 result.
    pairwise_results : list[PairwiseResult]
        Stage 2 results.
    mi_results : list[MIResult]
        Stage 3 results.
    plot_paths : dict[str, str], optional
        Mapping of plot name to file path; images are base64-embedded.
    quick : bool
        Whether Stage 3 was skipped.

    Returns
    -------
    str
        Complete HTML document as a string.
    """
    label, detail, color = _verdict(tvla_result, pairwise_results, mi_results)

    banner_gradient = (
        "linear-gradient(135deg, #c0392b, #e74c3c)"
        if color == "red"
        else "linear-gradient(135deg, #27ae60, #2ecc71)"
    )

    # ---- Embed images as base64 -------------------------------------------
    def _embed_image(path: str) -> str:
        data = pathlib.Path(path).read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f'<img src="data:image/png;base64,{b64}" style="max-width:100%; margin:12px 0;" />'

    images_html = ""
    if plot_paths:
        for name, path in plot_paths.items():
            try:
                images_html += f"<h4>{name.replace('_', ' ').title()}</h4>\n"
                images_html += _embed_image(path) + "\n"
            except FileNotFoundError:
                images_html += f"<p><em>Plot not found: {path}</em></p>\n"

    # ---- TVLA section -----------------------------------------------------
    tvla_status = "FAIL" if not tvla_result.passed else "PASS"
    tvla_status_color = "#e74c3c" if not tvla_result.passed else "#2ecc71"

    tvla_html = f"""
    <table class="data-table">
      <tr><td>Welch's t-statistic</td><td>{tvla_result.t_statistic:+.4f}</td></tr>
      <tr><td>|t|</td><td>{abs(tvla_result.t_statistic):.4f}</td></tr>
      <tr><td>Threshold</td><td>{tvla_result.threshold}</td></tr>
      <tr><td>p-value</td><td>{tvla_result.p_value:.2e}</td></tr>
      <tr><td>Variance ratio</td><td>{tvla_result.variance_ratio:.4f}</td></tr>
      <tr><td>n(fixed)</td><td>{tvla_result.n_fixed:,}</td></tr>
      <tr><td>n(random)</td><td>{tvla_result.n_random:,}</td></tr>
      <tr><td>Result</td>
          <td style="color:{tvla_status_color}; font-weight:bold;">{tvla_status}</td></tr>
    </table>
    """

    # ---- Pairwise section -------------------------------------------------
    if pairwise_results:
        pw_rows = ""
        for pr in pairwise_results:
            sig_color = "#e74c3c" if pr.any_significant else "#2ecc71"
            sig_label = "YES" if pr.any_significant else "NO"
            pw_rows += f"""
            <tr>
              <td>{pr.target_name}</td>
              <td>{pr.n_group0}</td><td>{pr.n_group1}</td>
              <td>{pr.welch_t:+.4f}</td><td>{pr.welch_p:.2e}</td>
              <td>{pr.cohens_d:.4f}</td><td>{pr.ks_p:.2e}</td>
              <td style="color:{sig_color}; font-weight:bold;">{sig_label}</td>
            </tr>"""
        pairwise_html = f"""
        <table class="data-table">
          <tr class="header-row">
            <th>Target</th><th>n(g0)</th><th>n(g1)</th>
            <th>Welch t</th><th>Welch p</th><th>Cohen's d</th>
            <th>KS p</th><th>Significant?</th>
          </tr>
          {pw_rows}
        </table>"""
    else:
        pairwise_html = "<p class='dimmed'>No secret labels available &mdash; stage skipped.</p>"

    # ---- MI section -------------------------------------------------------
    if quick:
        mi_html = "<p class='dimmed'>Skipped (--quick flag).</p>"
    elif mi_results:
        mi_rows = ""
        for mi in mi_results:
            sig_color = "#e74c3c" if mi.significant else "#2ecc71"
            sig_label = "YES" if mi.significant else "NO"
            mi_rows += f"""
            <tr>
              <td>{mi.target_name}</td>
              <td>{mi.observed_mi:.6f}</td>
              <td>{mi.null_mean:.6f}</td><td>{mi.null_std:.6f}</td>
              <td>{mi.p_value:.4f}</td><td>{mi.n_shuffles}</td>
              <td style="color:{sig_color}; font-weight:bold;">{sig_label}</td>
            </tr>"""
        mi_html = f"""
        <table class="data-table">
          <tr class="header-row">
            <th>Target</th><th>Observed MI</th><th>Null Mean</th>
            <th>Null Std</th><th>p-value</th><th>Shuffles</th>
            <th>Significant?</th>
          </tr>
          {mi_rows}
        </table>"""
    else:
        mi_html = "<p class='dimmed'>No secret labels available &mdash; stage skipped.</p>"

    # ---- Assemble full HTML -----------------------------------------------
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>sca-triage Report</title>
<style>
  :root {{
    --bg: #1a1a2e;
    --surface: #16213e;
    --text: #e0e0e0;
    --text-dim: #8a8a9a;
    --border: #2a2a4a;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 24px;
  }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  .banner {{
    background: {banner_gradient};
    color: #fff;
    padding: 28px 32px;
    border-radius: 8px;
    margin-bottom: 24px;
    text-align: center;
  }}
  .banner h1 {{ font-size: 1.6em; margin-bottom: 8px; }}
  .banner p {{ font-size: 0.95em; opacity: 0.9; }}
  details {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 16px;
    overflow: hidden;
  }}
  summary {{
    padding: 14px 20px;
    cursor: pointer;
    font-weight: 600;
    font-size: 1.05em;
    user-select: none;
  }}
  summary:hover {{ background: rgba(255,255,255,0.03); }}
  .section-body {{ padding: 4px 20px 20px; }}
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.88em;
    margin-top: 8px;
  }}
  .data-table td, .data-table th {{
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    text-align: left;
  }}
  .data-table tr:last-child td {{ border-bottom: none; }}
  .header-row th {{
    background: rgba(255,255,255,0.04);
    font-weight: 600;
    color: #82b1ff;
  }}
  .dimmed {{ color: var(--text-dim); font-style: italic; }}
  .footer {{
    text-align: center;
    color: var(--text-dim);
    font-size: 0.82em;
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
  }}
  img {{ border-radius: 6px; }}
</style>
</head>
<body>
<div class="container">

  <div class="banner">
    <h1>{label}</h1>
    <p>{detail}</p>
  </div>

  <details open>
    <summary>Stage 1: TVLA (Fixed-vs-Random)</summary>
    <div class="section-body">
      {tvla_html}
    </div>
  </details>

  <details open>
    <summary>Stage 2: Pairwise Secret-Group Decomposition</summary>
    <div class="section-body">
      {pairwise_html}
    </div>
  </details>

  <details {"open" if not quick else ""}>
    <summary>Stage 3: Permutation MI Test</summary>
    <div class="section-body">
      {mi_html}
    </div>
  </details>

  {"<details open><summary>Plots</summary><div class='section-body'>" + images_html + "</div></details>" if images_html else ""}

  <div class="footer">
    Generated by <strong>sca-triage</strong> &mdash; TVLA False-Positive Triage Tool
  </div>

</div>
</body>
</html>"""

    return html
