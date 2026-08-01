import { Disc3 } from "lucide-react";

const recentAdditions = [
  { artist: "Steely Dan", album: "Aja", year: "1977", format: "Vinyl, LP" },
  { artist: "Fleetwood Mac", album: "Rumours", year: "1977", format: "Vinyl, LP" },
  { artist: "Radiohead", album: "OK Computer", year: "1997", format: "Vinyl, 2xLP" },
  { artist: "Miles Davis", album: "Kind of Blue", year: "1959", format: "Vinyl, LP" },
  { artist: "Daft Punk", album: "Random Access Memories", year: "2013", format: "Vinyl, 2xLP" },
];

const recentSpins = [
  { artist: "Tame Impala", album: "Currents", year: "2015", format: "Vinyl, 2xLP" },
  { artist: "Khruangbin", album: "Con Todo El Mundo", year: "2018", format: "Vinyl, LP" },
  { artist: "Steely Dan", album: "Aja", year: "1977", format: "Vinyl, LP" },
  { artist: "Mac DeMarco", album: "Salad Days", year: "2014", format: "Vinyl, LP" },
  { artist: "Sade", album: "Diamond Life", year: "1984", format: "Vinyl, LP" },
];

const RecordList = ({ records }: { records: typeof recentAdditions }) => (
  <div>
    {records.map((record, i) => (
      <div
        key={`${record.album}-${i}`}
        className={i < records.length - 1 ? "music-record-row-bordered" : "music-record-row"}
      >
        <div className="music-record-icon">
          <Disc3 className="music-record-icon-svg" />
        </div>
        <div className="music-record-info">
          <p className="music-record-album">{record.album}</p>
          <p className="music-record-artist">{record.artist} · {record.year}</p>
          <p className="music-record-format">{record.format}</p>
        </div>
      </div>
    ))}
  </div>
);

const MusicWidget = () => {
  return (
    <div className="music-widget">
      <div className="music-header">
        <div className="music-header-left">
          <span className="music-brand">Discogs</span>
          <span className="music-badge">Collection</span>
        </div>
      </div>

      <div className="music-section-header">
        <div className="music-section-bar-orange" />
        <p className="music-section-label">Latest Additions</p>
        <span className="music-section-count">{recentAdditions.length}</span>
      </div>
      <RecordList records={recentAdditions} />

      <div className="music-divider" />

      <div className="music-spins-header">
        <div className="music-section-bar-green" />
        <p className="music-section-label">Latest Spins</p>
        <span className="music-section-count">{recentSpins.length}</span>
      </div>
      <RecordList records={recentSpins} />

      <div className="music-footer">
        <p className="music-footer-text">Placeholder — will connect to Discogs</p>
      </div>
    </div>
  );
};

export default MusicWidget;
