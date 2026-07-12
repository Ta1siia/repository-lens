const TOP_N = 40;

function trimGraph(graph, n = TOP_N) {
    const topNodes = [...graph.nodes].sort((a, b) => b.weight - a.weight).slice(0, n);
    const survivingNames = new Set(topNodes.map((node) => node.file));
    const edges = graph.edges.filter(
        (edge) => survivingNames.has(edge.file1) && survivingNames.has(edge.file2)
    );
    return { nodes: topNodes, edges };
}

function toD3Format(graph) {
    const nodes = graph.nodes.map((node) => ({ id: node.file, weight: node.weight }));
    const links = graph.edges.map((edge) => ({
        source: edge.file1,
        target: edge.file2,
        value: edge.weight,
    }));
    return { nodes, links };
}

function renderGraph(graph) {
    d3.select("#graph").selectAll("*").remove();

    const width = 800;
    const height = 600;
    const svg = d3.select("#graph").append("svg").attr("width", width).attr("height", height);

    const [minWeight, maxWeight] = d3.extent(graph.nodes, (d) => d.weight);
    const radiusScale = d3.scaleSqrt().domain([minWeight, maxWeight]).range([4, 20]);

    const simulation = d3
        .forceSimulation(graph.nodes)
        .force("link", d3.forceLink(graph.links).id((d) => d.id))
        .force("charge", d3.forceManyBody())
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collide", d3.forceCollide().radius((d) => radiusScale(d.weight) + 2));

    const link = svg.selectAll("line").data(graph.links).join("line").attr("stroke", "#999");

    const node = svg
        .selectAll("circle")
        .data(graph.nodes)
        .join("circle")
        .attr("r", (d) => radiusScale(d.weight))
        .attr("fill", "#69b3a2");

    simulation.on("tick", () => {
        link
            .attr("x1", (d) => d.source.x)
            .attr("y1", (d) => d.source.y)
            .attr("x2", (d) => d.target.x)
            .attr("y2", (d) => d.target.y);
        node
            .attr("cx", (d) => {
                const r = radiusScale(d.weight);
                return (d.x = Math.max(r, Math.min(width - r, d.x)));
            })
            .attr("cy", (d) => {
                const r = radiusScale(d.weight);
                return (d.y = Math.max(r, Math.min(height - r, d.y)));
            });
    });
}

document.getElementById("repo-form").addEventListener("submit", (event) => {
    event.preventDefault();

    const url = document.getElementById("repo-url").value;

    fetch("/graph", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
    })
        .then((response) => response.json())
        .then((data) => renderGraph(toD3Format(trimGraph(data))));
});
