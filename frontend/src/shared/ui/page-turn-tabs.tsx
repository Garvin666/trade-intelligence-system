import * as TabsPrimitive from "@radix-ui/react-tabs";
import {
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePrefersReducedMotion } from "@/shared/hooks/usePrefersReducedMotion";
import { TabsList, TabsTrigger } from "./tabs";

export interface PageTurnTab {
  value: string;
  label: ReactNode;
  content: ReactNode;
}

interface PageTurnTabsProps {
  tabs: PageTurnTab[];
  defaultValue?: string;
  className?: string;
  listClassName?: string;
}

export function PageTurnTabs({
  tabs,
  defaultValue,
  className,
  listClassName,
}: PageTurnTabsProps) {
  const reduced = usePrefersReducedMotion();
  const baseId = useId();
  const firstValue = tabs[0]?.value ?? "";
  const [active, setActive] = useState(defaultValue ?? firstValue);
  const stageRef = useRef<HTMLDivElement>(null);

  const handleChange = (nextValue: string) => {
    if (nextValue === active) return;
    setActive(nextValue);
  };

  useLayoutEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const root = document.documentElement;
    const previous = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";
    const top = Math.max(
      0,
      stage.getBoundingClientRect().top + window.scrollY - 72,
    );
    window.scrollTo(0, top);
    root.style.scrollBehavior = previous;
  }, [active]);

  const activeTab = tabs.find((tab) => tab.value === active) ?? tabs[0];

  return (
    <TabsPrimitive.Root
      value={active}
      onValueChange={handleChange}
      className={className}
    >
      <TabsList className={listClassName}>
        {tabs.map((tab) => (
          <TabsTrigger
            key={tab.value}
            value={tab.value}
            id={`${baseId}-trigger-${tab.value}`}
            aria-controls={`${baseId}-panel-${tab.value}`}
          >
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>

      <div ref={stageRef} className="relative mt-4">
        <div
          key={active}
          id={`${baseId}-panel-${active}`}
          role="tabpanel"
          aria-labelledby={`${baseId}-trigger-${active}`}
          className={
            reduced
              ? "outline-none"
              : "tab-fade-in relative z-20 outline-none"
          }
          tabIndex={0}
        >
          {activeTab?.content}
        </div>
      </div>
    </TabsPrimitive.Root>
  );
}
