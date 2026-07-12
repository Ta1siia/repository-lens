const TOP_N = 40;

function trimGraph(graph, n = TOP_N) {
  const topNodes = [...graph.nodes]
    .sort((a, b) => b.weight - a.weight)
    .slice(0, n);
  const survivingNames = new Set(topNodes.map(node => node.file));
  const edges = graph.edges.filter(
    edge => survivingNames.has(edge.file1) && survivingNames.has(edge.file2)
  );
  return { nodes: topNodes, edges };
}

function toD3Format(graph) {
  const nodes = graph.nodes.map(node => ({
    id: node.file,
    weight: node.weight,
  }));
  const links = graph.edges.map(edge => ({
    source: edge.file1,
    target: edge.file2,
    value: edge.weight,
  }));
  return { nodes, links };
}

function renderGraph(graph) {
  d3.select('#graph').selectAll('*').remove();

  const width = 1200;
  const height = 800;
  const svg = d3
    .select('#graph')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  const [minWeight, maxWeight] = d3.extent(graph.nodes, d => d.weight);
  const radiusScale = d3
    .scaleSqrt()
    .domain([minWeight, maxWeight])
    .range([4, 20]);
  graph.nodes.forEach(d => (d.r = radiusScale(d.weight)));

  const simulation = d3
    .forceSimulation(graph.nodes)
    .force(
      'link',
      d3.forceLink(graph.links).id(d => d.id)
    )
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force(
      'collide',
      d3.forceCollide().radius(d => d.r + 15)
    );

  const g = svg.append('g');

  const link = g
    .selectAll('line')
    .data(graph.links)
    .join('line')
    .attr('stroke', '#999');

  const node = g
    .selectAll('circle')
    .data(graph.nodes)
    .join('circle')
    .attr('r', d => d.r)
    .attr('fill', '#69b3a2');

  const label = g
    .selectAll('text')
    .data(graph.nodes)
    .join('text')
    .text(d => d.id.split('/').pop())
    .attr('font-size', 10)
    .attr('dx', 8)
    .attr('dy', 4);

  svg.call(
    d3.zoom().on('zoom', event => {
      g.attr('transform', event.transform);
    })
  );

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
    node
      .attr('cx', d => (d.x = Math.max(d.r, Math.min(width - d.r, d.x))))
      .attr('cy', d => (d.y = Math.max(d.r, Math.min(height - d.r, d.y))));
    label.attr('x', d => d.x).attr('y', d => d.y);
  });
}

function showError(message) {
  const container = document.getElementById('graph');
  container.innerHTML = '';
  const p = document.createElement('p');
  p.className = 'error';
  p.style.color = 'red';
  p.textContent = message;
  container.appendChild(p);
}

document.getElementById('repo-form').addEventListener('submit', event => {
  event.preventDefault();

  const url = document.getElementById('repo-url').value;
  const submitBtn = document.getElementById('submit-btn');

  submitBtn.disabled = true;
  submitBtn.textContent = 'Loading…';

  fetch('/graph', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
    .then(response =>
      response.json().then(data => {
        if (!response.ok) {
          throw new Error(data.error || `Request failed: ${response.status}`);
        }
        return data;
      })
    )
    .then(data => renderGraph(toD3Format(trimGraph(data))))
    .catch(error => showError(error.message))
    .finally(() => {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Visualize';
    });
});
