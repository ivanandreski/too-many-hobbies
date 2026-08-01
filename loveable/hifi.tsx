const gear = [
  {
    category: "Turntable",
    name: "Placeholder Model",
    description: "The centerpiece of the setup. Belt-drive with a moving magnet cartridge — warm, detailed sound straight from the groove.",
    icon: "💿",
  },
  {
    category: "Receiver",
    name: "Placeholder Model",
    description: "Powers everything. An integrated amplifier with clean 2x80W output that handles both analog and digital sources without breaking a sweat.",
    icon: "🎛️",
  },
  {
    category: "Speakers",
    name: "Placeholder Model",
    description: "2-way bookshelf speakers with a bass reflex port. They fill the room surprisingly well for their size — punchy lows and crisp highs.",
    icon: "🔊",
  },
  {
    category: "Cassette Deck",
    name: "Placeholder Model",
    description: "There's something magical about tape. Dolby B/C noise reduction keeps things clean, and making mixtapes is still one of my favorite things.",
    icon: "📼",
  },
  {
    category: "CD Player",
    name: "Placeholder Model",
    description: "Sometimes you just want to drop a disc in and press play. Single disc, digital output — simple and reliable.",
    icon: "💽",
  },
];

const HifiWidget = () => {
  return (
    <div className="hifi-list">
      {gear.map((item, i) => {
        const isEven = i % 2 === 0;
        return (
          <div
            key={item.category}
            className={`hifi-item ${!isEven ? "hifi-item-reverse" : ""}`}
          >
            <div className="hifi-image">{item.icon}</div>
            <div className="hifi-text">
              <p className="hifi-category">{item.category}</p>
              <h3 className="hifi-name">{item.name}</h3>
              <p className="hifi-description">{item.description}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default HifiWidget;
