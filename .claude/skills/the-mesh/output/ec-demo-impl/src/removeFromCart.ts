/**
 * removeFromCart - カートから商品を削除
 * Generated from TRIR Spec
 */

import {
  RepositoryContext,
  CartItemNotFoundError,
} from './types';

interface RemoveFromCartInput {
  cartItemId: string;
}

interface RemoveFromCartOutput {
  success: boolean;
}

/**
 * カートから商品を削除する
 *
 * @post Product.stock が cartItem.quantity 分増加する（在庫復元）
 * @post CartItem が削除される
 */
export async function removeFromCart(
  input: RemoveFromCartInput,
  ctx: RepositoryContext
): Promise<RemoveFromCartOutput> {
  const { cartItemId } = input;

  // Get cart item
  const cartItem = await ctx.cartItemRepository.get(cartItemId);
  if (!cartItem) {
    throw new CartItemNotFoundError();
  }

  // Get product to restore stock
  const product = await ctx.productRepository.get(cartItem.productId);
  if (product) {
    // Post-action 1: Restore product stock
    await ctx.productRepository.update(cartItem.productId, {
      stock: product.stock + cartItem.quantity,
    });
  }

  // Post-action 2: Delete cart item
  await ctx.cartItemRepository.delete(cartItemId);

  return { success: true };
}
