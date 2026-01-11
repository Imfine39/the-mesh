/**
 * addToCart - 商品をカートに追加
 *
 * Generated from TRIR Spec: ec-demo
 *
 * Pre-conditions:
 *   - quantity > 0 (数量は1以上を指定してください)
 *
 * Post-conditions:
 *   1. CartItem created with:
 *      - id: generateId()
 *      - cartId: input.cartId
 *      - productId: input.productId
 *      - quantity: input.quantity
 *      - unitPrice: product.price
 *   2. Product.stock decremented by quantity
 */

import {
  AddToCartInput,
  AddToCartOutput,
  CartItem,
  InvalidQuantityError,
  OutOfStockError,
  ProductNotFoundError,
} from './types';
import { RepositoryContext, generateId } from './repositories';

export async function addToCart(
  input: AddToCartInput,
  ctx: RepositoryContext
): Promise<AddToCartOutput> {
  const { cartId, productId, quantity } = input;

  // === Pre-condition: quantity > 0 ===
  if (!(quantity > 0)) {
    throw new InvalidQuantityError();
  }

  // === Fetch required entities ===
  const product = await ctx.products.get(productId);
  if (!product) {
    throw new ProductNotFoundError();
  }

  // === Additional check: stock availability ===
  if (product.stock < quantity) {
    throw new OutOfStockError();
  }

  // === Post-condition 1: Create CartItem ===
  const cartItem: CartItem = {
    id: generateId(),
    cartId: cartId,
    productId: productId,
    quantity: quantity,
    unitPrice: product.price,
  };

  await ctx.cartItems.create(cartItem);

  // === Post-condition 2: Decrement Product stock ===
  await ctx.products.update(productId, {
    stock: product.stock - quantity,
  });

  return { cartItem };
}
