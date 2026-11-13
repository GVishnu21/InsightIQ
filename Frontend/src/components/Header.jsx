function Header() {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            IQ
          </span>
          <div>
            <div className="brand-name">InsightIQ</div>
            <div className="brand-tagline">Ask questions about your CSV in plain English</div>
          </div>
        </div>
        <span className="pill">Gemini + DuckDB</span>
      </div>
    </header>
  );
}

export default Header;
