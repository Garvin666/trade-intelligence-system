import logoUrl from "@/assets/logo-ship.png?inline";

export function LoadingScreen() {
  return (
    <div className="loading-screen">
      <img
        className="loading-screen__logo"
        src={logoUrl}
        width={44}
        height={44}
        alt="远帆智品"
      />
      <p className="loading-screen__text">远帆智品 · 数据引擎载入中</p>
    </div>
  );
}
