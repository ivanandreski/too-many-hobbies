import { Box } from "lucide-react";

const recentSets = [
  { number: "76916", name: "Porsche 963", theme: "Speed Champions", pieces: 280, year: "2023" },
  { number: "76917", name: "2 Fast 2 Furious Nissan Skyline GT-R", theme: "Speed Champions", pieces: 319, year: "2023" },
  { number: "76914", name: "Ferrari 812 Competizione", theme: "Speed Champions", pieces: 261, year: "2023" },
  { number: "76911", name: "007 Aston Martin DB5", theme: "Speed Champions", pieces: 298, year: "2023" },
  { number: "76906", name: "1970 Ferrari 512 M", theme: "Speed Champions", pieces: 291, year: "2022" },
  { number: "76908", name: "Lamborghini Countach", theme: "Speed Champions", pieces: 262, year: "2022" },
];

const LegoWidget = () => {
  return (
    <div className="lego-widget">
      <div className="lego-header">
        <div className="lego-header-left">
          <span className="lego-brand">LEGO</span>
          <span className="lego-badge">My Sets</span>
        </div>
        <span className="lego-total">
          {recentSets.reduce((sum, s) => sum + s.pieces, 0).toLocaleString()} pcs total
        </span>
      </div>

      <div>
        {recentSets.map((set, i) => (
          <div
            key={set.number}
            className={`lego-set-row ${i % 2 === 0 ? "lego-set-row-even" : "lego-set-row-odd"} ${i < recentSets.length - 1 ? "lego-set-row-bordered" : ""}`}
          >
            <div className="lego-set-icon">
              <Box className="lego-set-icon-svg" />
            </div>
            <div className="lego-set-info">
              <p className="lego-set-name">{set.name}</p>
              <p className="lego-set-meta">{set.number} · {set.pieces.toLocaleString()} pieces · {set.year}</p>
            </div>
            <span className="lego-set-theme">{set.theme}</span>
          </div>
        ))}
      </div>

      <div className="lego-footer">
        <p className="lego-footer-text">Placeholder — recent builds</p>
      </div>
    </div>
  );
};

export default LegoWidget;
