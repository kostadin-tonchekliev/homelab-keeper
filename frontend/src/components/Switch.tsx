interface Props {
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}

export function Switch({ checked, onChange, disabled }: Props) {
  return (
    <label className="switch">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="slider" />
    </label>
  );
}
