import React, { useState, useRef, useEffect } from 'react';

export interface DropdownOption {
  value: string;
  label: string;
  shortLabel?: string;
  color?: string;
  icon?: string;
  badge?: string;
}

interface CustomDropdownProps {
  label: string;
  value: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  ariaLabel?: string;
  className?: string;
  align?: 'left' | 'right';
}

export const CustomDropdown: React.FC<CustomDropdownProps> = ({
  label,
  value,
  options,
  onChange,
  ariaLabel,
  className = '',
  align = 'left',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);
  const isSelected = Boolean(value);

  // Close when clicking outside
  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent | TouchEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
      document.addEventListener('touchstart', handleOutsideClick);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('touchstart', handleOutsideClick);
    };
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const handleSelect = (optValue: string) => {
    onChange(optValue);
    setIsOpen(false);
  };

  const displayLabel = isSelected
    ? selectedOption?.shortLabel || selectedOption?.label || label
    : label;

  return (
    <div
      ref={containerRef}
      className={`custom-dropdown-container ${className} ${isOpen ? 'dropdown-open' : ''}`}
    >
      <button
        type="button"
        aria-label={ariaLabel || label}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
        className={`custom-dropdown-trigger ${isSelected ? 'pill-active' : ''}`}
      >
        {selectedOption?.color && (
          <span
            className="dropdown-color-dot"
            style={{ backgroundColor: selectedOption.color }}
          />
        )}
        {selectedOption?.icon && (
          <span className="dropdown-trigger-icon">{selectedOption.icon}</span>
        )}
        <span className="dropdown-trigger-text">{displayLabel}</span>
        <svg
          className={`dropdown-chevron ${isOpen ? 'rotate' : ''}`}
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {isOpen && (
        <div
          role="listbox"
          aria-label={ariaLabel || label}
          className={`custom-dropdown-menu align-${align}`}
        >
          {options.map((opt) => {
            const isItemActive = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                role="option"
                aria-selected={isItemActive}
                onClick={() => handleSelect(opt.value)}
                className={`custom-dropdown-item ${isItemActive ? 'item-active' : ''}`}
              >
                <div className="dropdown-item-left">
                  {opt.color && (
                    <span
                      className="dropdown-color-dot"
                      style={{ backgroundColor: opt.color }}
                    />
                  )}
                  {opt.icon && (
                    <span className="dropdown-item-icon">{opt.icon}</span>
                  )}
                  <span className="dropdown-item-label">{opt.label}</span>
                </div>
                {isItemActive && (
                  <span className="dropdown-checkmark">✓</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

