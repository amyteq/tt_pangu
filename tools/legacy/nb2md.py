#!/usr/bin/env python

import argparse
from pathlib import Path
import nbformat
import pypandoc


def convert_ipynb_to_md(input_path):
    # 1. 路径处理
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"错误: 找不到文件 {input_path}")
        return
    output_path = input_path.with_suffix(".md")

    # 2. 读取 Notebook
    with open(input_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    md_content = []

    # 3. 遍历每一个 Cell
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            # Markdown Cell 直接添加
            md_content.append(cell.source)

        elif cell.cell_type == "code":
            # 处理代码块：强制添加 ```python 标识
            md_content.append(f"```python\n{cell.source}\n```")

            # 处理输出 (Outputs)
            for output in cell.get("outputs", []):
                # A. 处理执行结果 (如 Pandas DataFrame 的 HTML 表格)
                if output.output_type in ["execute_result", "display_data"]:
                    data = output.get("data", {})

                    if "text/html" in data:
                        # 核心步骤：使用 Pandoc 将 HTML 字符串转换为 GFM (Markdown) 表格
                        html_table = data["text/html"]
                        try:
                            # 明确告诉 Pandoc：输入是 html，输出是 gfm
                            md_table = pypandoc.convert_text(html_table, "gfm", format="html")
                            md_content.append(md_table.strip())
                        except Exception as e:
                            print(f"表格转换失败，保留原 HTML。错误: {e}")
                            md_content.append(html_table)

                    elif "text/plain" in data:
                        # 如果没有 HTML，取普通文本输出
                        md_content.append(f"\n{data['text/plain']}\n")

                # B. 处理标准输出 (如 print 打印的内容)
                elif output.output_type == "stream":
                    md_content.append(f"\n{output.text}\n")

                # C. 处理错误信息
                elif output.output_type == "error":
                    md_content.append(f"```\n{'/'.join(output.traceback)}\n```")

        # 每个 cell 之间加个换行
        md_content.append("\n---\n")

    # 4. 合并并保存文件
    final_md = "\n".join(md_content)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_md)

    print(f"转换成功！已生成: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将 ipynb 转换为 md，确保 HTML 表格转为 Markdown 表格。")
    parser.add_argument("input", help="输入的 .ipynb 文件路径")

    args = parser.parse_args()
    convert_ipynb_to_md(args.input)
