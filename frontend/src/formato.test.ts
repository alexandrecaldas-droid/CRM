import { describe, expect, it } from "vitest";
import { duracao, localParaISO, qsHelper, telefone } from "./testeUtil";

describe("formatação", () => {
  it("formata telefone E.164 brasileiro", () => {
    expect(telefone("+5511987654321")).toBe("(11) 98765-4321");
    expect(telefone("+14155550100")).toBe("+14155550100");
  });
  it("formata duração", () => {
    expect(duracao(90000)).toBe("1d 1h");
    expect(duracao(300)).toBe("5 min");
  });
  it("converte horário de São Paulo para UTC", () => {
    expect(localParaISO("2026-11-23T09:00")).toBe("2026-11-23T12:00:00.000Z");
  });
  it("monta query string com listas e ignora vazios", () => {
    expect(qsHelper({ a: [1, 2], b: "", c: false, d: "x" })).toBe("?a=1&a=2&d=x");
  });
});
