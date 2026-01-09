// 実験: TypeScriptコードから依存関係を自動抽出できるか

// ============================================
// State (DBスキーマ相当)
// ============================================
type Invoice = {
  id: string;
  customerId: string;
  amount: number;
  taxAmount: number;
  discountRate: number;
  status: "open" | "closed";
};

type Payment = {
  id: string;
  customerId: string;
  amount: number;
};

type Allocation = {
  id: string;
  invoiceId: string;
  paymentId: string;
  amount: number;
};

// ============================================
// Derived (計算式)
// ============================================

/** 税・割引考慮後の請求額 */
function netAmount(invoice: Invoice): number {
  return invoice.amount * (1 - invoice.discountRate) + invoice.taxAmount;
}

/** 請求の残額 */
function remaining(invoice: Invoice, allocations: Allocation[]): number {
  const allocated = allocations
    .filter(a => a.invoiceId === invoice.id)
    .reduce((sum, a) => sum + a.amount, 0);
  return netAmount(invoice) - allocated;
}

/** 入金の未消込残高 */
function paymentBalance(payment: Payment, allocations: Allocation[]): number {
  const allocated = allocations
    .filter(a => a.paymentId === payment.id)
    .reduce((sum, a) => sum + a.amount, 0);
  return payment.amount - allocated;
}

// ============================================
// Function (API仕様)
// ============================================

type AllocatePaymentInput = {
  invoiceId: string;
  paymentId: string;
  amount: number;
};

type AllocatePaymentResult =
  | { success: true; allocation: Allocation; invoiceClosed: boolean }
  | { success: false; error: "OVER_ALLOCATION" | "CUSTOMER_MISMATCH" | "INVOICE_NOT_OPEN" };

function allocatePayment(
  input: AllocatePaymentInput,
  invoice: Invoice,
  payment: Payment,
  allocations: Allocation[]
): AllocatePaymentResult {
  // Pre conditions
  if (invoice.status !== "open") {
    return { success: false, error: "INVOICE_NOT_OPEN" };
  }
  if (invoice.customerId !== payment.customerId) {
    return { success: false, error: "CUSTOMER_MISMATCH" };
  }
  const rem = remaining(invoice, allocations);
  if (rem < input.amount) {
    return { success: false, error: "OVER_ALLOCATION" };
  }

  // Post: create allocation
  const allocation: Allocation = {
    id: `ALLOC-${Date.now()}`,
    invoiceId: input.invoiceId,
    paymentId: input.paymentId,
    amount: input.amount,
  };

  // Post: check if invoice should close
  const newRemaining = rem - input.amount;
  const invoiceClosed = newRemaining === 0;

  return { success: true, allocation, invoiceClosed };
}

// ============================================
// このコードから抽出したい依存関係:
//
// netAmount:
//   - invoice.amount
//   - invoice.discountRate
//   - invoice.taxAmount
//
// remaining:
//   - netAmount()
//   - allocation.invoiceId
//   - allocation.amount
//   - invoice.id
//
// paymentBalance:
//   - payment.amount
//   - allocation.paymentId
//   - allocation.amount
//
// allocatePayment:
//   - invoice.status
//   - invoice.customerId
//   - payment.customerId
//   - remaining()
// ============================================
