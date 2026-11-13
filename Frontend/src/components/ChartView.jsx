import Plotly from "plotly.js-basic-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

// The "basic" Plotly bundle supports bar, line, scatter and pie charts, which is
// everything the backend produces, at a fraction of the size of the full library.
const Plot = createPlotlyComponent(Plotly);

// The backend sends a ready-made Plotly figure ({ data, layout }). This component
// only draws it, so chart decisions stay in one place (backend/charts.py).
//
// `onImage` (optional) receives a PNG of the finished chart. The PDF report uses
// it, because html2canvas cannot reliably copy a live Plotly chart into a PDF.
function ChartView({ chart, onImage }) {
  if (!chart?.figure) return null;

  const { data, layout } = chart.figure;

  const handleInitialized = (_figure, graphDiv) => {
    if (!onImage) return;
    Plotly.toImage(graphDiv, { format: "png", width: 900, height: 400 })
      .then(onImage)
      .catch(() => {}); // a missing picture only affects the PDF, never the page
  };

  return (
    <Plot
      data={data}
      layout={{ ...layout, autosize: true }}
      config={{ displaylogo: false, responsive: true }}
      useResizeHandler
      onInitialized={handleInitialized}
      style={{ width: "100%", height: "400px" }}
    />
  );
}

export default ChartView;
