/**
 * EC Demo - Generated Types from TRIR Spec
 *
 * Entities: Product, Cart, CartItem, Order, OrderItem
 */

// === Entity Types ===

export interface Product {
  id: string;
  name: string;
  price: number;      // 税抜価格（円）
  stock: number;      // 在庫数
}

export interface Cart {
  id: string;
  userId: string;
  totalAmount?: number; // 合計金額
}

export interface CartItem {
  id: string;
  cartId: string;     // ref: Cart
  productId: string;  // ref: Product
  quantity: number;
  unitPrice: number;
}

export type OrderStatus = 'PENDING' | 'PAID' | 'SHIPPED' | 'DELIVERED' | 'CANCELLED';

export interface Order {
  id: string;
  userId: string;
  totalAmount: number;
  status: OrderStatus;
  createdAt: Date;
}

export interface OrderItem {
  id: string;
  orderId: string;    // ref: Order
  productId: string;
  productName: string;
  quantity: number;
  unitPrice: number;
}

// === Command Input Types ===

export interface AddToCartInput {
  cartId: string;
  productId: string;
  quantity: number;   // min: 1
}

export interface AddToCartOutput {
  cartItem: CartItem;
}

export interface RemoveFromCartInput {
  cartItemId: string;
}

export interface RemoveFromCartOutput {
  success: boolean;
}

export interface CheckoutInput {
  cartId: string;
  userId: string;
}

export interface CheckoutOutput {
  order: Order;
}

export interface CancelOrderInput {
  orderId: string;
}

export interface CancelOrderOutput {
  order: Order;
}

// === Error Types ===

export class InvalidQuantityError extends Error {
  code = 'INVALID_QUANTITY';
  status = 400;
  constructor() { super('数量が無効です'); }
}

export class OutOfStockError extends Error {
  code = 'OUT_OF_STOCK';
  status = 400;
  constructor() { super('在庫不足'); }
}

export class ProductNotFoundError extends Error {
  code = 'PRODUCT_NOT_FOUND';
  status = 404;
  constructor() { super('商品が見つかりません'); }
}

export class EmptyCartError extends Error {
  code = 'EMPTY_CART';
  status = 400;
  constructor() { super('カートが空です'); }
}

export class CartNotFoundError extends Error {
  code = 'CART_NOT_FOUND';
  status = 404;
  constructor() { super('カートが見つかりません'); }
}

export class OrderNotFoundError extends Error {
  code = 'ORDER_NOT_FOUND';
  status = 404;
  constructor() { super('注文が見つかりません'); }
}

export class CannotCancelError extends Error {
  code = 'CANNOT_CANCEL';
  status = 400;
  constructor() { super('キャンセルできない状態です'); }
}
