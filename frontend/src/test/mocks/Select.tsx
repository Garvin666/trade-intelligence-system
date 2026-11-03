export interface MockSelectOption {
  value: string;
  label: string;
}

interface MockSelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: MockSelectOption[];
  placeholder?: string;
  ariaLabel?: string;
}

export function Select({
  value,
  onValueChange,
  options,
  ariaLabel,
}: MockSelectProps) {
  return (
    <select
      aria-label={ariaLabel}
      value={value}
      onChange={(event) => onValueChange(event.target.value)}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
