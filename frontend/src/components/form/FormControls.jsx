import "./FormControls.css";

export function FieldShell({ label, help, error, required, children, wide }) {
  return (
    <label className={"form-field" + (wide ? " wide" : "")}>
      <span className="form-field-label">
        {label}
        {required && <span className="req">*</span>}
      </span>
      {children}
      {help && <span className="form-field-help">{help}</span>}
      {error && <span className="form-field-error">{error}</span>}
    </label>
  );
}

export function TextInput({ label, help, error, required, wide, ...props }) {
  return (
    <FieldShell label={label} help={help} error={error} required={required} wide={wide}>
      <input type="text" className={error ? "invalid" : ""} {...props} />
    </FieldShell>
  );
}

export function NumberInput({ label, help, error, required, wide, ...props }) {
  return (
    <FieldShell label={label} help={help} error={error} required={required} wide={wide}>
      <input type="number" className={error ? "invalid" : ""} {...props} />
    </FieldShell>
  );
}

export function SelectInput({ label, help, error, required, wide, options, ...props }) {
  return (
    <FieldShell label={label} help={help} error={error} required={required} wide={wide}>
      <select className={error ? "invalid" : ""} {...props}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

// Free-text input with quick-pick suggestions, not a locked dropdown -- the
// backend accepts any customer_id/merchant_id (bootstrapping a new record if
// it's never been seen), so constraining entry to a fixed sample list would
// be more restrictive than the real API.
export function ComboInput({ label, help, error, required, wide, options, listId, ...props }) {
  return (
    <FieldShell label={label} help={help} error={error} required={required} wide={wide}>
      <input type="text" list={listId} className={error ? "invalid" : ""} {...props} />
      <datalist id={listId}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </datalist>
    </FieldShell>
  );
}

export function DateTimeInput({ label, help, error, required, wide, ...props }) {
  return (
    <FieldShell label={label} help={help} error={error} required={required} wide={wide}>
      <input type="datetime-local" className={error ? "invalid" : ""} {...props} />
    </FieldShell>
  );
}

export function SliderInput({ label, help, value, onChange, min = 0, max = 100 }) {
  return (
    <FieldShell label={label} help={help}>
      <div className="slider-row">
        <input
          type="range"
          min={min}
          max={max}
          value={value}
          onChange={onChange}
          style={{ "--fill-pct": `${((value - min) / (max - min)) * 100}%` }}
        />
        <span className="slider-value tabular">{value}</span>
      </div>
    </FieldShell>
  );
}

export function ToggleInput({ label, help, checked, onChange }) {
  return (
    <div className="toggle-field">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        className={"toggle" + (checked ? " on" : "")}
        onClick={() => onChange(!checked)}
      >
        <span className="toggle-knob" />
      </button>
      <div className="toggle-text">
        <span className="form-field-label">{label}</span>
        {help && <span className="form-field-help">{help}</span>}
      </div>
    </div>
  );
}
