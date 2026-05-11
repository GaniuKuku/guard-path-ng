class SQLPolicyEngine:

    def evaluate(self, risks: list, query: str, role: str = "engineer"):
        decision = {
            "allowed": True,
            "reason": [],
            "risk_level": "LOW"
        }

        # 1. GLOBAL BLOCK: Schema Destruction
        destructive_risks = [r for r in risks if r["category"] == "DESTRUCTIVE"]
        if destructive_risks:
            decision["allowed"] = False
            decision["risk_level"] = "CRITICAL"
            decision["reason"].append(f"Blocked Destructive SQL: {destructive_risks[0]['operation']}")
            return decision

        # 2. GLOBAL BLOCK: Unbounded Mass Operations
        mass_ops = [r for r in risks if r["category"] == "UNSAFE_MASS_OPERATION"]
        if mass_ops:
            decision["allowed"] = False
            decision["risk_level"] = "CRITICAL"
            decision["reason"].append(f"Blocked Mass Operation: {mass_ops[0]['reason']}")
            return decision

        # 3. ROLE-BASED BLOCK: Analysts cannot write
        write_risks = [r for r in risks if r["category"] == "WRITE"]
        if write_risks:
            if role == "analyst":
                decision["allowed"] = False
                decision["risk_level"] = "HIGH"
                decision["reason"].append("Read-only role enforced. Writes blocked.")
            else:
                decision["risk_level"] = "MEDIUM"
                decision["reason"].append("Targeted write operation permitted for engineer.")

        return decision
