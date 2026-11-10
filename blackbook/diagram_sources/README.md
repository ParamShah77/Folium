# Diagram sources

The PNG figures in `../figures/` are drawn by `../make_figures.py` (matplotlib), which also plots
every result chart directly from the repository's evaluation JSON files.

The files here are equivalent, editable definitions of the design diagrams:
`.mmd` files are Mermaid (paste into https://mermaid.live or render with `mmdc -i file.mmd -o file.png`),
and `fig5_5_usecase.puml` is PlantUML. Charts in Chapters 4, 8 and 9 have no separate source because they
are generated from data by `make_figures.py`.
